# -*- coding: utf-8 -*-
"""Tests del asistente de IA.

Ninguno sale a la red: ``ai_provider.call_provider`` se sustituye por una
función que devuelve lo que quiera cada prueba. Lo que se verifica es
exactamente lo que este módulo controla — qué se envía, qué se acepta de vuelta
y quién puede pedirlo — no la calidad de la respuesta del modelo.
"""
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from odoo.addons.al_project_gantt_base.tests.common import GanttCommon

PROVIDER_PATH = 'odoo.addons.al_project_gantt_ai.services.ai_provider.call_provider'


@tagged('post_install', '-at_install')
class TestGanttAi(GanttCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.task_a = cls._create_task('IA — tarea A', day_offset=0, duration_days=2)
        cls.task_b = cls._create_task('IA — tarea B', day_offset=5, duration_days=3)
        cls.ai = cls.env['al.gantt.ai']
        # Los ajustes son parámetros del sistema, es decir estado compartido de
        # la instalación: el test fija los que necesita en vez de dar por bueno
        # lo que haya configurado quien use esta base.
        cls._set_param('provider', 'anthropic')
        cls._set_param('model', 'claude-opus-5')
        cls._set_key('sk-test-key')

    @classmethod
    def _set_param(cls, key, value):
        cls.env['ir.config_parameter'].sudo().set_param('al_gantt_ai.' + key, value)

    @classmethod
    def _set_key(cls, value):
        cls._set_param('api_key', value)

    def _config(self, **overrides):
        config = self.ai._get_config()
        config.update(overrides)
        return config

    # ------------------------------------------------------------------
    # Configuración y disponibilidad
    # ------------------------------------------------------------------
    def test_status_needs_a_key(self):
        """Sin clave el panel no debe ofrecerse."""
        self._set_key('')
        self.assertFalse(self.ai.get_status()['enabled'])
        self._set_key('sk-test-key')
        status = self.ai.get_status()
        self.assertTrue(status['enabled'])
        self.assertEqual(status['provider'], 'anthropic')
        # La clave nunca sale del servidor.
        self.assertNotIn('api_key', status)

    def test_status_echoes_the_configured_provider(self):
        self._set_param('provider', 'deepseek')
        self._set_param('model', 'deepseek-chat')
        status = self.ai.get_status()
        self.assertEqual(status['provider'], 'deepseek')
        self.assertEqual(status['model'], 'deepseek-chat')

    def test_ask_without_key_is_a_clear_error(self):
        self._set_key('')
        with self.assertRaises(UserError):
            self.ai.ask({'question': '¿Hay retrasos?', 'task_ids': [self.task_a.id]})
        self._set_key('sk-test-key')

    def test_ask_requires_a_question(self):
        with self.assertRaises(UserError):
            self.ai.ask({'question': '   ', 'task_ids': [self.task_a.id]})

    def test_ask_rejects_a_huge_question(self):
        with self.assertRaises(UserError):
            self.ai.ask({'question': 'x' * 5000, 'task_ids': [self.task_a.id]})

    # ------------------------------------------------------------------
    # Seguridad
    # ------------------------------------------------------------------
    def test_portal_user_cannot_ask(self):
        portal = self.env['res.users'].create({
            'name': 'Portal IA',
            'login': 'portal.ia@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            self.env['al.gantt.ai'].with_user(portal).get_status()

    # ------------------------------------------------------------------
    # Contexto: qué se envía al proveedor
    # ------------------------------------------------------------------
    def test_context_only_carries_summary_fields(self):
        context = self.ai._build_context([self.task_a.id], self._config())
        task = context['by_id'][self.task_a.id]
        self.assertEqual(
            set(task) - {'assignees'},
            {'id', 'name', 'project', 'start', 'end', 'state', 'progress',
             'depends_on', 'editable'},
            "El contexto no debe llevar más campos de los declarados.",
        )

    def test_context_drops_ids_the_user_cannot_see(self):
        """Un id inventado no puede colarse en el prompt."""
        context = self.ai._build_context([self.task_a.id, 999999], self._config())
        self.assertEqual(list(context['by_id']), [self.task_a.id])
        self.assertTrue(context['warnings'])

    def test_context_respects_the_limit(self):
        context = self.ai._build_context(
            [self.task_a.id, self.task_b.id], self._config(context_limit=1),
        )
        self.assertEqual(len(context['tasks']), 1)
        self.assertTrue(context['truncated'])

    def test_assignees_can_be_withheld(self):
        self.task_a.user_ids = [(6, 0, [self.gantt_user.id])]
        with_names = self.ai._build_context([self.task_a.id], self._config(share_assignees=True))
        self.assertIn('assignees', with_names['by_id'][self.task_a.id])
        without = self.ai._build_context([self.task_a.id], self._config(share_assignees=False))
        self.assertNotIn('assignees', without['by_id'][self.task_a.id])
        self.assertFalse(without['assignable_users'])

    def test_system_prompt_lists_the_tasks(self):
        context = self.ai._build_context([self.task_a.id], self._config())
        prompt = self.ai._build_system_prompt(context, self._config())
        self.assertIn('#%s IA — tarea A' % self.task_a.id, prompt)
        self.assertIn('propose_changes', prompt)

    def test_history_starts_with_a_user_turn(self):
        """Los dos proveedores rechazan un historial que empiece por el asistente."""
        messages = self.ai._build_messages(
            [{'role': 'assistant', 'content': 'huérfano'}], 'nueva pregunta',
        )
        self.assertEqual([message['role'] for message in messages], ['user'])

    # ------------------------------------------------------------------
    # Validación de lo que devuelve el modelo
    # ------------------------------------------------------------------
    def _proposal(self, changes):
        context = self.ai._build_context([self.task_a.id, self.task_b.id], self._config())
        return self.ai._normalize_proposal({'summary': 's', 'changes': changes}, context)

    def test_proposal_over_an_unknown_task_is_dropped(self):
        proposals, warnings = self._proposal([{'task_id': 999999, 'reason': 'r'}])
        self.assertFalse(proposals)
        self.assertTrue(warnings)

    def test_proposal_with_a_bad_date_is_dropped(self):
        proposals, warnings = self._proposal([
            {'task_id': self.task_a.id, 'reason': 'r', 'start': 'la semana que viene'},
        ])
        self.assertFalse(proposals)
        self.assertTrue(warnings)

    def test_proposal_with_start_after_end_is_dropped(self):
        proposals, warnings = self._proposal([{
            'task_id': self.task_a.id, 'reason': 'r',
            'start': '2026-05-10T08:00:00Z', 'end': '2026-05-01T08:00:00Z',
        }])
        self.assertFalse(proposals)
        self.assertTrue(warnings)

    def test_progress_is_clamped(self):
        proposals, _warnings = self._proposal([
            {'task_id': self.task_a.id, 'reason': 'r', 'progress': 250},
        ])
        self.assertEqual(proposals[0]['values']['progress'], 100.0)

    def test_valid_dates_become_a_changeset_item(self):
        proposals, warnings = self._proposal([{
            'task_id': self.task_a.id, 'reason': 'se solapa',
            'start': '2026-05-01T08:00:00Z', 'end': '2026-05-03T08:00:00Z',
        }])
        self.assertFalse(warnings)
        self.assertEqual(len(proposals), 1)
        values = proposals[0]['values']
        self.assertEqual(values['id'], self.task_a.id)
        self.assertEqual(values['start'], '2026-05-01T08:00:00Z')
        self.assertTrue(proposals[0]['labels'])

    def test_unknown_assignee_is_ignored(self):
        proposals, warnings = self._proposal([
            {'task_id': self.task_a.id, 'reason': 'r', 'user_ids': [999999]},
        ])
        self.assertFalse(proposals)
        self.assertTrue(warnings)

    def test_garbage_output_does_not_crash(self):
        self.assertEqual(self.ai._normalize_proposal(None, {'by_id': {}}), ([], []))
        self.assertEqual(self.ai._normalize_proposal('nope', {'by_id': {}}), ([], []))

    # ------------------------------------------------------------------
    # Flujo completo (proveedor simulado)
    # ------------------------------------------------------------------
    def test_ask_returns_answer_and_proposals(self):
        raw = {
            'summary': 'Mover la tarea A',
            'changes': [{
                'task_id': self.task_a.id, 'reason': 'libera al equipo',
                'start': '2026-05-01T08:00:00Z', 'end': '2026-05-03T08:00:00Z',
            }],
        }
        with patch(PROVIDER_PATH, return_value=('Aquí va la respuesta.', raw, {})):
            result = self.ai.ask({
                'question': '¿Puedo mover la tarea A?',
                'task_ids': [self.task_a.id, self.task_b.id],
            })
        self.assertEqual(result['answer'], 'Aquí va la respuesta.')
        self.assertEqual(len(result['proposals']), 1)
        self.assertEqual(result['context']['task_count'], 2)

    def test_ask_needs_visible_tasks(self):
        with patch(PROVIDER_PATH, return_value=('', None, {})):
            with self.assertRaises(UserError):
                self.ai.ask({'question': '¿Y esto?', 'task_ids': []})

    def test_proposals_are_applied_through_the_base_contract(self):
        """La escritura es la misma que la del arrastre: nada de sudo ni atajos."""
        raw = {
            'summary': 's',
            'changes': [{
                'task_id': self.task_a.id, 'reason': 'r',
                'start': '2026-05-01T08:00:00Z', 'end': '2026-05-03T08:00:00Z',
            }],
        }
        with patch(PROVIDER_PATH, return_value=('ok', raw, {})):
            result = self.ai.ask({'question': 'mueve A', 'task_ids': [self.task_a.id]})

        changeset = {'tasks': {'update': [result['proposals'][0]['values']]}}
        self.env['project.project'].apply_gantt_changes(changeset)

        if self.end_field:
            self.assertEqual(self.task_a[self.end_field].strftime('%Y-%m-%d'), '2026-05-03')

    def test_proposal_on_a_task_without_write_access_is_dropped(self):
        """El servidor filtra antes de proponer; la escritura vuelve a filtrar."""
        readonly_project = self.env['project.project'].create({
            'name': 'IA — solo lectura',
            'privacy_visibility': 'followers',
        })
        hidden = self._create_task('IA — ajena', project=readonly_project)
        # Aunque el cliente pida su id, la tarea ajena no entra en el prompt:
        # el contexto se relee con el usuario real, sin sudo.
        context = self.ai.with_user(self.gantt_user)._build_context(
            [self.task_a.id, hidden.id], self._config(),
        )
        self.assertIn(self.task_a.id, context['by_id'])
        self.assertNotIn(hidden.id, context['by_id'])

    def test_provider_failure_surfaces_as_user_error(self):
        with patch(PROVIDER_PATH, side_effect=UserError('proveedor caído')):
            with self.assertRaises(UserError):
                self.ai.ask({'question': 'hola', 'task_ids': [self.task_a.id]})

    # ------------------------------------------------------------------
    # Fechas
    # ------------------------------------------------------------------
    def test_iso_round_trip(self):
        parsed = self.ai._as_datetime('2026-05-01T10:30:00+02:00')
        self.assertEqual(self.ai._to_iso(parsed), '2026-05-01T08:30:00Z')

    def test_short_label_of_a_missing_date(self):
        self.assertEqual(self.ai._short(None), '—')

    def test_short_label_uses_the_user_timezone(self):
        """La etiqueta se lee junto a la rejilla, que muestra hora local."""
        ai = self.ai.with_context(tz='America/Lima')  # UTC-5
        self.assertEqual(ai._short('2026-05-01T08:00:00Z'), '01/05/2026 03:00')

    def test_context_dependencies_stay_inside_the_view(self):
        self.task_b.depend_on_ids = [(4, self.task_a.id)]
        both = self.ai._build_context([self.task_a.id, self.task_b.id], self._config())
        self.assertEqual(both['by_id'][self.task_b.id]['depends_on'], [self.task_a.id])
        # Si la predecesora no se está viendo, la dependencia no se menciona.
        alone = self.ai._build_context([self.task_b.id], self._config())
        self.assertEqual(alone['by_id'][self.task_b.id]['depends_on'], [])


@tagged('post_install', '-at_install')
class TestProviderRequests(GanttCommon):
    """Qué se manda por el cable a cada proveedor (sin red).

    Se parchea ``requests.post``, no el conector: lo que interesa comprobar es
    justo lo que el conector construye — URL, cabeceras y los campos que cada
    API nombra de forma distinta.
    """

    def _capture(self, provider, response_payload):
        from odoo.addons.al_project_gantt_ai.services import ai_provider

        captured = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return response_payload

        def fake_post(url, headers=None, json=None, timeout=None):
            captured.update(url=url, headers=headers, body=json, timeout=timeout)
            return FakeResponse()

        config = {
            'provider': provider,
            'api_key': 'sk-test',
            'model': ai_provider.DEFAULT_MODEL[provider],
            'base_url': None,
            'effort': 'medium',
            'max_tokens': 8000,
            'timeout': 90,
        }
        with patch.object(ai_provider.requests, 'post', fake_post):
            result = ai_provider.call_provider(self.env, config, 'sistema', [
                {'role': 'user', 'content': 'hola'},
            ])
        return captured, result

    @staticmethod
    def _chat_completion(arguments='{"summary": "s", "changes": []}'):
        return {
            'model': 'x',
            'choices': [{'message': {
                'content': 'respuesta',
                'tool_calls': [{'function': {
                    'name': 'propose_changes', 'arguments': arguments,
                }}],
            }}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2},
        }

    def test_deepseek_hits_its_own_endpoint(self):
        captured, _result = self._capture('deepseek', self._chat_completion())
        self.assertEqual(captured['url'], 'https://api.deepseek.com/v1/chat/completions')
        self.assertEqual(captured['headers']['Authorization'], 'Bearer sk-test')
        self.assertEqual(captured['body']['model'], 'deepseek-chat')

    def test_deepseek_uses_max_tokens_not_the_openai_name(self):
        """DeepSeek conserva `max_tokens`; OpenAI lo renombró."""
        captured, _result = self._capture('deepseek', self._chat_completion())
        self.assertEqual(captured['body']['max_tokens'], 8000)
        self.assertNotIn('max_completion_tokens', captured['body'])

    def test_openai_uses_max_completion_tokens(self):
        captured, _result = self._capture('openai', self._chat_completion())
        self.assertEqual(captured['url'], 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(captured['body']['max_completion_tokens'], 8000)
        self.assertNotIn('max_tokens', captured['body'])

    def test_openai_compatibles_declare_the_tool(self):
        for provider in ('openai', 'deepseek'):
            captured, _result = self._capture(provider, self._chat_completion())
            names = [tool['function']['name'] for tool in captured['body']['tools']]
            self.assertEqual(names, ['propose_changes'], provider)
            self.assertEqual(captured['body']['tool_choice'], 'auto', provider)

    def test_effort_is_only_sent_to_anthropic(self):
        """`output_config` no existe en las APIs compatibles con OpenAI."""
        for provider in ('openai', 'deepseek'):
            captured, _result = self._capture(provider, self._chat_completion())
            self.assertNotIn('output_config', captured['body'], provider)

        captured, _result = self._capture('anthropic', {
            'model': 'x', 'content': [{'type': 'text', 'text': 'ok'}], 'usage': {},
        })
        self.assertEqual(captured['body']['output_config'], {'effort': 'medium'})
        self.assertEqual(captured['headers']['x-api-key'], 'sk-test')
        self.assertEqual(captured['headers']['anthropic-version'], '2023-06-01')

    def test_deepseek_tool_call_is_parsed(self):
        payload = self._chat_completion(
            '{"summary": "mover", "changes": [{"task_id": 1, "reason": "r"}]}'
        )
        _captured, (answer, proposal, usage) = self._capture('deepseek', payload)
        self.assertEqual(answer, 'respuesta')
        self.assertEqual(proposal['changes'][0]['task_id'], 1)
        self.assertEqual(usage['input_tokens'], 10)

    def test_malformed_tool_arguments_do_not_crash(self):
        _captured, (answer, proposal, _usage) = self._capture(
            'deepseek', self._chat_completion('{esto no es json'),
        )
        self.assertEqual(answer, 'respuesta')
        self.assertIsNone(proposal)

    def test_empty_choices_names_the_provider(self):
        from odoo.addons.al_project_gantt_ai.services import ai_provider

        with self.assertRaises(UserError) as caught:
            self._capture('deepseek', {'choices': []})
        self.assertIn('DeepSeek', str(caught.exception))
        self.assertIn('deepseek', ai_provider.API_KEY_DOCS)

    def test_every_provider_declares_its_metadata(self):
        """Un proveedor nuevo sin metadatos rompería los ajustes en silencio."""
        from odoo.addons.al_project_gantt_ai.services import ai_provider

        providers = dict(
            self.env['res.config.settings']._fields['al_gantt_ai_provider'].selection
        )
        for provider in providers:
            self.assertIn(provider, ai_provider.DEFAULT_MODEL, provider)
            self.assertIn(provider, ai_provider.DEFAULT_BASE_URL, provider)
            self.assertIn(provider, ai_provider.PROVIDER_LABEL, provider)
            self.assertIn(provider, ai_provider.API_KEY_DOCS, provider)


@tagged('post_install', '-at_install')
class TestAiProviderErrors(GanttCommon):
    """Traducción de fallos HTTP a mensajes accionables (sin red)."""

    def _error(self, status, payload=None):
        from odoo.addons.al_project_gantt_ai.services import ai_provider

        class FakeResponse:
            status_code = status
            text = 'boom'

            def json(self):
                if payload is None:
                    raise ValueError('no json')
                return payload

        return str(ai_provider._build_http_error(self.env, FakeResponse(), 'Anthropic'))

    def test_unauthorized_points_at_the_settings(self):
        self.assertIn('clave', self._error(401).lower())

    def test_rate_limit_suggests_retrying(self):
        self.assertIn('429', self._error(429))

    def test_unknown_model_names_the_model(self):
        message = self._error(404, {'error': {'message': 'claude-inventado'}})
        self.assertIn('claude-inventado', message)

    def test_server_error_is_not_blamed_on_the_user(self):
        self.assertIn('disponible', self._error(503).lower())

    def test_non_json_body_does_not_crash(self):
        self.assertTrue(self._error(400))
