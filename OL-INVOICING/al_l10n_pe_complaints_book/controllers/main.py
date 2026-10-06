import time
from datetime import timedelta

from werkzeug.exceptions import NotFound

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.tools import email_normalize
from odoo.tools.misc import consteq, hmac

from odoo.addons.portal.controllers.portal import CustomerPortal

#: Adjuntos que admite el formulario (proyecto de 2026, art. 5-A): PDF e imágenes.
ATTACHMENT_MIMETYPES = {'application/pdf', 'image/jpeg', 'image/png'}
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024
#: Protección contra envíos automáticos sin captcha (el libro no puede
#: exigir registro ni obstáculos): segundos mínimos entre abrir y enviar el
#: formulario y hojas por IP y hora.
MIN_FILL_SECONDS = 3
MAX_PER_IP_PER_HOUR = 5
FORM_FIELDS = (
    'consumer_name', 'consumer_doc_type', 'consumer_doc_number', 'consumer_address',
    'consumer_phone', 'consumer_email', 'guardian_name', 'guardian_doc_number',
    'guardian_address', 'guardian_phone', 'guardian_email', 'good_type', 'good_description',
    'order_reference', 'claim_type', 'detail', 'consumer_request', 'preferred_response_channel',
)


class ComplaintsBookController(CustomerPortal):

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _complaint_books(self):
        """Libros publicados en el sitio web actual."""
        return request.website._l10n_pe_complaint_books()

    @staticmethod
    def _form_token(timestamp):
        return hmac(request.env(su=True), 'l10n_pe_complaint_form', str(timestamp))

    def _render_form(self, book, values=None, errors=None):
        timestamp = int(time.time())
        books = self._complaint_books()
        return request.render('al_l10n_pe_complaints_book.complaint_form_page', {
            'book': book,
            'books': books,
            # sudo: el visitante anónimo no lee la compañía, pero la hoja debe mostrar
            # razón social, RUC y dirección (Reglamento, art. 5).
            'company': book.sudo().company_id,
            'values': values or {},
            'errors': errors or {},
            'form_ts': timestamp,
            'form_token': self._form_token(timestamp),
            'today': fields.Date.context_today(request.env.user),
        })

    def _validate(self, post):
        """Errores por campo; los del art. 5 hacen que la hoja «no se tenga por presentada»."""
        errors = {}
        required = {
            'consumer_name': _('Indique su nombre.'),
            'consumer_doc_number': _('Indique su documento de identidad.'),
            'detail': _('Describa su reclamo o queja.'),
            'consumer_request': _('Indique su pedido.'),
        }
        for field, message in required.items():
            if not (post.get(field) or '').strip():
                errors[field] = message
        if not ((post.get('consumer_address') or '').strip() or (post.get('consumer_email') or '').strip()):
            errors['consumer_address'] = _('Indique su domicilio o su correo electrónico.')
        email = (post.get('consumer_email') or '').strip()
        if email and not email_normalize(email):
            errors['consumer_email'] = _('El correo electrónico no es válido.')
        if post.get('preferred_response_channel', 'email') == 'email' and not email:
            errors['consumer_email'] = _('Indique su correo para recibir la constancia y la respuesta.')
        doc_type, doc_number = post.get('consumer_doc_type'), (post.get('consumer_doc_number') or '').strip()
        if doc_type == 'dni' and doc_number and not (len(doc_number) == 8 and doc_number.isdigit()):
            errors['consumer_doc_number'] = _('El DNI debe tener 8 dígitos.')
        if doc_type == 'ruc' and doc_number and not (len(doc_number) == 11 and doc_number.isdigit()):
            errors['consumer_doc_number'] = _('El RUC debe tener 11 dígitos.')
        if post.get('is_minor') and not (post.get('guardian_name') or '').strip():
            errors['guardian_name'] = _('Indique el padre, la madre o el representante.')
        amount = (post.get('amount_claimed') or '').replace(',', '').strip()
        if amount:
            try:
                if float(amount) < 0:
                    raise ValueError
            except ValueError:
                errors['amount_claimed'] = _('El monto no es válido.')
        if not post.get('consumer_confirmed'):
            errors['consumer_confirmed'] = _('Confirme el envío de la hoja.')
        return errors

    def _is_bot(self, post):
        """Campo trampa, firma del formulario y tiempo mínimo de llenado."""
        if post.get('website_url'):
            return True
        try:
            timestamp = int(post.get('form_ts') or 0)
        except ValueError:
            return True
        if not consteq(self._form_token(timestamp), post.get('form_token') or ''):
            return True
        return time.time() - timestamp < MIN_FILL_SECONDS

    def _too_many(self, ip_address):
        # sudo: contar envíos por IP no requiere leer las hojas como visitante.
        complaints_sudo = request.env['l10n_pe.complaint'].sudo()
        since = fields.Datetime.now() - timedelta(hours=1)
        return complaints_sudo.search_count([
            ('consumer_ip', '=', ip_address), ('create_date', '>=', since)]) >= MAX_PER_IP_PER_HOUR

    def _attachments(self):
        files = request.httprequest.files.getlist('attachments')
        files = [f for f in files if f and f.filename]
        if len(files) > MAX_ATTACHMENTS:
            raise ValidationError(_('Puede adjuntar como máximo %s archivos.', MAX_ATTACHMENTS))
        result = []
        for file in files:
            content = file.read()
            if len(content) > MAX_ATTACHMENT_SIZE:
                raise ValidationError(_('El archivo %s supera los 5 MB.', file.filename))
            if file.mimetype not in ATTACHMENT_MIMETYPES:
                raise ValidationError(_('El archivo %s no es PDF, JPG ni PNG.', file.filename))
            result.append((file.filename, content, file.mimetype))
        return result

    # ------------------------------------------------------------------
    # Formulario público (sin registro ni inicio de sesión)
    # ------------------------------------------------------------------

    @http.route(['/libro-reclamaciones'], type='http', auth='public', website=True, sitemap=True)
    def complaints_book_form(self, libro=None, **kwargs):
        books = self._complaint_books()
        if not books:
            raise NotFound()
        book = books.filtered(lambda b: str(b.id) == str(libro))[:1] or books[:1]
        return self._render_form(book)

    @http.route(['/libro-reclamaciones/enviar'], type='http', auth='public', website=True,
                methods=['POST'], sitemap=False)
    def complaints_book_submit(self, **post):
        books = self._complaint_books()
        book = books.filtered(lambda b: str(b.id) == str(post.get('book_id')))[:1]
        if not book:
            raise NotFound()
        if self._is_bot(post):
            return self._render_form(book, post, {'form': _(
                'No pudimos registrar la hoja. Vuelva a intentarlo en unos segundos.')})
        ip_address = request.httprequest.remote_addr
        if self._too_many(ip_address):
            return self._render_form(book, post, {'form': _(
                'Se registraron demasiadas hojas desde su conexión. Inténtelo más tarde o '
                'solicite el libro en el establecimiento.')})
        errors = self._validate(post)
        if errors:
            return self._render_form(book, post, errors)
        try:
            files = self._attachments()
        except ValidationError as error:
            return self._render_form(book, post, {'attachments': error.args[0]})
        values = {field: (post.get(field) or '').strip() or False for field in FORM_FIELDS}
        values.update({
            'book_id': book.id,
            'channel': 'web',
            'consumer_doc_type': post.get('consumer_doc_type') or 'dni',
            'good_type': post.get('good_type') or 'product',
            'claim_type': post.get('claim_type') or 'claim',
            'preferred_response_channel': post.get('preferred_response_channel') or 'email',
            'is_minor': bool(post.get('is_minor')),
            'amount_claimed': float((post.get('amount_claimed') or '0').replace(',', '') or 0),
            'consumer_confirmed': True,
            'consumer_ip': ip_address,
        })
        if not values['is_minor']:
            for field in ('guardian_name', 'guardian_doc_number', 'guardian_address',
                          'guardian_phone', 'guardian_email'):
                values[field] = False
        try:
            # sudo: el consumidor registra la hoja sin cuenta (el libro no puede exigir
            # registro); los datos se validaron arriba y en las restricciones del modelo.
            complaint_sudo = request.env['l10n_pe.complaint'].sudo().with_context(
                tz=book.sudo().company_id.partner_id.tz or 'America/Lima').create(values)
        except ValidationError as error:
            return self._render_form(book, post, {'form': error.args[0]})
        for name, content, mimetype in files:
            attachment_sudo = request.env['ir.attachment'].sudo().create({
                'name': name, 'raw': content, 'mimetype': mimetype,
                'res_model': complaint_sudo._name, 'res_id': complaint_sudo.id,
            })
            complaint_sudo.attachment_ids = [(4, attachment_sudo.id)]
        return request.redirect(complaint_sudo.get_portal_url())

    # ------------------------------------------------------------------
    # Constancia y seguimiento (enlace firmado, sin inicio de sesión)
    # ------------------------------------------------------------------

    def _complaint_from_token(self, complaint_id, access_token):
        try:
            return self._document_check_access('l10n_pe.complaint', complaint_id, access_token)
        except (AccessError, MissingError):
            raise NotFound()

    @http.route(['/libro-reclamaciones/hoja/<int:complaint_id>'], type='http', auth='public',
                website=True, sitemap=False)
    def complaint_page(self, complaint_id, access_token=None, **kwargs):
        complaint_sudo = self._complaint_from_token(complaint_id, access_token)
        return request.render('al_l10n_pe_complaints_book.complaint_status_page', {
            'complaint': complaint_sudo,
            'access_token': access_token,
            'company': complaint_sudo.company_id,
        })

    @http.route(['/libro-reclamaciones/hoja/<int:complaint_id>/pdf'], type='http', auth='public',
                website=True, sitemap=False)
    def complaint_pdf(self, complaint_id, access_token=None, **kwargs):
        complaint_sudo = self._complaint_from_token(complaint_id, access_token)
        report = request.env.ref('al_l10n_pe_complaints_book.action_report_complaint')
        pdf, dummy = request.env['ir.actions.report'].sudo().with_context(
            tz=complaint_sudo._report_tz())._render_qweb_pdf(report, complaint_sudo.ids)
        filename = 'Hoja de reclamacion %s.pdf' % complaint_sudo.name
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', http.content_disposition(filename)),
        ])
