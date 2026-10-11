"""Run with Python 3.12, Flask, Aegis client 3.3.0 / models 2.8.0 installed.

python -m unittest discover -s skills/aegis-nextjs-frontend/tests -v
Executes the published Markdown snippets; no live Aegis calls or Docker pushes.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from flask import Flask, g
from byteforge_aegis_client import AegisApiError, AegisNetworkError

REFS = Path(__file__).resolve().parents[1] / 'references'
SITE = '01900000-0000-7000-8000-000000000002'
OTHER_SITE = '01900000-0000-7000-8000-000000000099'
USER = '01900000-0000-7000-8000-000000000003'


def snippet(file, heading):
    text = (REFS / file).read_text().split(heading, 1)[1]
    return re.search(r'```[^\n]*\n(.*?)\n```', text, re.S).group(1)


def module(name, file, heading):
    result = types.ModuleType(name)
    exec(compile(snippet(file, heading), file, 'exec'), result.__dict__)
    return result


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'AEGIS_API_URL': 'https://auth.example.com', 'AEGIS_SITE_ID': SITE})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.auth = module('aegis_auth_test', 'backend-auth-templates.md', '## Flask:')
        self.app = Flask(__name__)

        @self.app.get('/protected')
        @self.auth.aegis_auth_required
        def protected():
            return {'uuid': g.current_user.uuid}

        self.client = self.app.test_client()
        # Patch only the transport: real SDK construction, typed me(), and
        # model decoding execute, catching API/config/model-shape drift.
        self.http = patch('byteforge_aegis_client._http.HttpSession.request')
        self.request = self.http.start()
        self.addCleanup(self.http.stop)
        self.request.return_value = {
            'uuid': USER, 'site_uuid': SITE, 'email': 'user@example.com',
            'is_verified': True, 'role': 'user', 'created_at': 1, 'updated_at': 1,
        }

    def get(self):
        return self.client.get('/protected', headers={'Authorization': 'Bearer test-token'})

    def test_model_identity_and_positive_cache(self):
        self.assertEqual(self.get().json, {'uuid': USER})
        self.assertEqual(self.get().status_code, 200)
        self.assertEqual(self.request.call_count, 1)

    def test_cross_site_rejected_and_negative_cached(self):
        self.request.return_value['site_uuid'] = OTHER_SITE
        self.assertEqual(self.get().status_code, 401)
        self.assertEqual(self.get().status_code, 401)
        self.assertEqual(self.request.call_count, 1)

    def test_rejections_and_outages(self):
        for status in (400, 401, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                self.auth.resolve_token.cache.clear()
                self.request.reset_mock()
                self.request.side_effect = AegisApiError(status, 'simulated')
                expected = 503 if status in (429, 500, 503) else 401
                self.assertEqual(self.get().status_code, expected)
                self.assertEqual(self.get().status_code, expected)
                self.assertEqual(self.request.call_count, 2 if expected == 503 else 1)
        self.request.side_effect = AegisNetworkError('simulated')
        self.assertEqual(self.get().status_code, 503)

    def test_cache_expiry_rechecks_authority(self):
        with patch.object(self.auth.time, 'monotonic', return_value=100):
            self.assertEqual(self.get().status_code, 200)
        self.request.side_effect = AegisApiError(401, 'revoked')
        with patch.object(self.auth.time, 'monotonic', return_value=131):
            self.assertEqual(self.get().status_code, 401)

    def test_configuration_and_empty_token_fail_closed(self):
        for site in ('', '42', 'bad-uuid'):
            with self.assertRaises(ValueError):
                self.auth.AegisTokenResolver('https://auth.example.com', site)
        self.assertEqual(self.client.get('/protected').status_code, 401)
        self.assertEqual(self.client.get('/protected', headers={'Authorization': 'Bearer  '}).status_code, 401)
        self.request.assert_not_called()


class SiblingProxyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'AEGIS_API_URL': 'https://auth.example.com',
                                          'AEGIS_SITE_ID': SITE, 'AEGIS_TENANT_API_KEY': 'test-key'})
        self.env.start()
        self.addCleanup(self.env.stop)
        helper = module('sibling_client', 'tenant-api-key-templates.md', '### Flask client:')
        self.modules = patch.dict(sys.modules, {'lib': types.ModuleType('lib'), 'lib.aegis': helper})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.routes = module('sibling_routes', 'tenant-api-key-templates.md', '### Flask routes:')
        self.app = Flask(__name__)
        self.app.register_blueprint(self.routes.blp)
        self.client = self.app.test_client()
        self.http = patch('byteforge_aegis_client._http.HttpSession.request')
        self.request = self.http.start()
        self.addCleanup(self.http.stop)

    def test_all_six_operations_preserve_json_rejection_and_server_site(self):
        self.request.side_effect = AegisApiError(401, 'rejected')
        for operation, (_, required, _) in self.routes.OPERATIONS.items():
            with self.subTest(operation=operation):
                body = {key: 'test-value' for key in required}
                body.update(site_id=OTHER_SITE, role='admin')
                response = self.client.post('/api/auth/' + operation, json=body)
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.is_json)
                sent = self.request.call_args.args[2]
                self.assertEqual(sent['site_id'], SITE)
                self.assertNotIn('role', sent)

    def test_registration_success_and_outage_statuses(self):
        self.request.return_value = {'message': 'Registration initiated'}
        response = self.client.post('/api/auth/register', json={'email': 'test@example.com'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json, {'message': 'Registration initiated'})
        for error, expected in [(AegisApiError(429, 'limited'), 429),
                                (AegisApiError(500, 'down'), 503),
                                (AegisNetworkError('down'), 503)]:
            self.request.side_effect = error
            response = self.client.post('/api/auth/login', json={'email': 'u@example.com', 'password': 'test'})
            self.assertEqual(response.status_code, expected)
            self.assertTrue(response.is_json)

    def test_bad_input_unknown_routes_and_missing_config(self):
        for body in (None, [], {}, {'email': 42, 'password': 'test'}):
            response = self.client.post('/api/auth/login', json=body)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post('/api/auth/arbitrary', json={}).status_code, 404)
        self.request.assert_not_called()
        del os.environ['AEGIS_SITE_ID']
        response = self.client.post('/api/auth/login', json={'email': 'u@example.com', 'password': 'test'})
        self.assertEqual(response.status_code, 503)


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'AEGIS_WEBHOOK_SECRET': 'test-only-secret', 'AEGIS_SITE_ID': SITE})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.webhook = module('webhook_test', 'webhook-templates.md', '## Flask receiver:')
        self.app = Flask(__name__)
        self.app.register_blueprint(self.webhook.blp)
        self.client = self.app.test_client()
        self.events = []
        self.app.extensions['aegis_identity_store'] = types.SimpleNamespace(apply_event=self.events.append)

    def post(self, event='user.verified', site=SITE, age=0, header_event=None, signature=None, body=None):
        timestamp = str(int(time.time()) - age)
        payload = dict(event_id='01900000-0000-7000-8000-000000000001', event_type=event,
                       site_uuid=site, user_uuid=USER, email='user@example.com', timestamp=1)
        raw = body if body is not None else json.dumps(payload)
        digest = hmac.new(b'test-only-secret', f'{timestamp}.{raw}'.encode(), hashlib.sha256).hexdigest()
        return self.client.post('/api/webhooks/aegis', data=raw, content_type='application/json', headers={
            'X-Aegis-Timestamp': timestamp, 'X-Aegis-Event': header_event or event,
            'X-Aegis-Signature': signature if signature is not None else 'sha256=' + digest,
        })

    def test_verification_and_deletion_dispatch(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post(event='user.deleted').status_code, 200)
        self.assertEqual([e['event_type'] for e in self.events], ['user.verified', 'user.deleted'])

    def test_retry_uses_fresh_signing_time_not_event_time(self):
        self.assertEqual(self.post().status_code, 200)  # payload timestamp is 1
        self.assertEqual(self.post(age=301).status_code, 401)

    def test_relabel_and_wrong_site_never_mutate(self):
        self.assertEqual(self.post(header_event='user.deleted').status_code, 401)
        self.assertEqual(self.post(site=OTHER_SITE).status_code, 403)
        self.assertEqual(self.events, [])

    def test_invalid_payload_and_signature_never_crash(self):
        for signature in ('', 'sha256=x', 'sha256=' + 'z' * 64, 'sha256=' + 'é' * 64):
            self.assertEqual(self.post(signature=signature).status_code, 401)
        for body in ('[]', 'null', 'not json', '{}'):
            self.assertIn(self.post(body=body).status_code, (400, 401))
        self.assertEqual(self.events, [])

    def test_no_false_success_when_persistence_missing_or_fails(self):
        del self.app.extensions['aegis_identity_store']
        self.assertEqual(self.post().status_code, 503)
        def fail(_):
            raise RuntimeError('simulated rollback')
        self.app.extensions['aegis_identity_store'] = types.SimpleNamespace(apply_event=fail)
        self.assertEqual(self.post().status_code, 503)

    def test_unknown_events_acknowledged_without_mutation(self):
        self.assertEqual(self.post(event='future.event').status_code, 200)
        self.assertEqual(self.events, [])

    def test_missing_site_config_is_not_a_bypass(self):
        os.environ['AEGIS_SITE_ID'] = ''
        self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.events, [])


class DockerCredentialTests(unittest.TestCase):
    def test_secret_scoped_git_config_handles_both_ssh_transports(self):
        dockerfile = snippet('docker-templates.md', '## Dockerfile')
        command = dockerfile.split('RUN --mount=type=secret,id=cr_pat,required=true ', 1)[1].split('\n\n', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = root / 'cr_pat'
            secret.write_text('fake-build-secret')
            global_config = root / 'gitconfig'
            bindir = root / 'bin'
            bindir.mkdir()
            npm = bindir / 'npm'
            npm.write_text('#!/usr/bin/env bash\nset -e\n'
                           'git config --get-all url.https://github.com/.insteadOf > "$TEST_REWRITES"\n'
                           'git config --get-urlmatch http.extraheader https://github.com/example/repo > "$TEST_HEADER"\n')
            npm.chmod(0o755)
            env = {**os.environ, 'PATH': str(bindir) + ':' + os.environ['PATH'],
                   'GIT_CONFIG_GLOBAL': str(global_config), 'GIT_CONFIG_NOSYSTEM': '1',
                   'TEST_REWRITES': str(root / 'rewrites'), 'TEST_HEADER': str(root / 'header')}
            subprocess.run(['sh', '-c', command.replace('/run/secrets/cr_pat', str(secret))],
                           cwd=root, env=env, check=True, capture_output=True)
            self.assertEqual((root / 'rewrites').read_text().splitlines(),
                             ['ssh://git@github.com/', 'git@github.com:'])
            expected = base64.b64encode(b'x-access-token:fake-build-secret').decode()
            self.assertEqual((root / 'header').read_text().strip(), 'Authorization: Basic ' + expected)
            self.assertFalse(global_config.exists())
            self.assertNotIn('ARG CR_PAT', dockerfile)
            self.assertNotIn('ENV CR_PAT', dockerfile)


class PublishScriptTests(unittest.TestCase):
    def test_directory_version_secret_and_failure_behavior(self):
        script = snippet('build-publish-template.md', '## build-publish.sh')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / 'project with spaces'
            project.mkdir()
            (project / 'build-publish.sh').write_text(script.replace('{registry_url}', 'example.test/app'))
            bindir = root / 'bin'
            bindir.mkdir()
            docker = bindir / 'docker'
            docker.write_text('#!/usr/bin/env bash\nprintf "%s|%s\\n" "$PWD" "$*" >> "$TEST_LOG"\n'
                              'if [[ "${FAIL_COMMAND:-}" == "$1" ]]; then exit 7; fi\n')
            docker.chmod(0o755)
            log = root / 'docker.log'
            env = {**os.environ, 'PATH': str(bindir) + ':' + os.environ['PATH'], 'TEST_LOG': str(log),
                   'AUTH_PROXY_MODE': 'nextjs', 'CR_PAT': 'fake-secret-never-in-args', 'NEXT_PUBLIC_AEGIS_API_URL': 'https://auth.example.com',
                   'NEXT_PUBLIC_SITE_DOMAIN': 'app.example.com'}
            def run(*args, **extra):
                return subprocess.run(['bash', str(project / 'build-publish.sh'), *args], cwd=root,
                                      env={**env, **extra}, capture_output=True, text=True)
            subprocess.run(['bash', '-n', str(project / 'build-publish.sh')], check=True)
            self.assertEqual(run('--no-cache').returncode, 0)
            self.assertEqual((project / 'VERSION').read_text(), '1\n')
            self.assertFalse((root / 'VERSION').exists())
            calls = log.read_text()
            self.assertIn('build --no-cache --secret id=cr_pat,env=CR_PAT', calls)
            self.assertNotIn(env['CR_PAT'], calls)
            self.assertTrue(all(line.startswith(str(project) + '|') for line in calls.splitlines()))
            for command in ('build', 'tag', 'push'):
                log.write_text('')
                self.assertNotEqual(run(FAIL_COMMAND=command).returncode, 0)
                self.assertEqual((project / 'VERSION').read_text(), '1\n')
                if command == 'build':
                    self.assertEqual(len(log.read_text().splitlines()), 1)
            log.write_text('')
            self.assertNotEqual(run('--unexpected').returncode, 0)
            self.assertNotEqual(run(CR_PAT='').returncode, 0)
            self.assertEqual(log.read_text(), '')
            self.assertNotEqual(run(AUTH_PROXY_MODE='sibling', NEXT_PUBLIC_BACKEND_API_URL='').returncode, 0)
            self.assertEqual(log.read_text(), '')
            result = run(AUTH_PROXY_MODE='sibling', NEXT_PUBLIC_BACKEND_API_URL='https://api.example.com',
                         NEXT_PUBLIC_AEGIS_SITE_ID=SITE)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text()
            self.assertIn('--build-arg NEXT_PUBLIC_BACKEND_API_URL=https://api.example.com', calls)
            self.assertIn('--build-arg NEXT_PUBLIC_AEGIS_SITE_ID=' + SITE, calls)
            self.assertNotIn(env['CR_PAT'], calls)


if __name__ == '__main__':
    unittest.main()
