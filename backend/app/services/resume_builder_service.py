"""Profile-owned resume drafts, explicit profile imports, and text PDF export."""
from datetime import datetime, timezone
import json

from ..schemas_resume_builder import ResumeDocument
from .resume_builder_store import ResumeBuilderStore


class ResumeBuilderConflict(Exception):
    pass


class ResumeBuilderInvalid(Exception):
    pass


SECTIONS = ['summary', 'education', 'skills', 'projects', 'experience', 'internships',
            'certifications', 'achievements']
PERSONAL_FIELDS = ['name', 'email', 'phone', 'location', 'linkedin', 'github', 'portfolio']
SKILL_GROUPS = ['programming_languages', 'frameworks', 'databases', 'cloud', 'ai_ml', 'web_technologies',
                'tools', 'other_skills']


def empty_document(revision=0):
    return ResumeDocument.model_validate({'revision': revision}).model_dump(mode='json')


def _nonempty(value):
    return value is not None and str(value).strip() != ''


def import_profile_document(profile):
    """Copy only explicit saved profile values; absence remains empty."""
    document = empty_document()
    personal = profile.get('personal') or {}
    for field in PERSONAL_FIELDS:
        value = personal.get(field)
        if _nonempty(value):
            document['personal'][field] = str(value)
            document['personal_sources'][field] = 'profile'

    education = profile.get('education') or {}
    if any(_nonempty(education.get(field)) for field in ('degree', 'branch', 'college', 'graduation_year', 'cgpa')):
        document['education'].append({
            'entry_id': 'profile-education-0', 'source': 'profile',
            'institution': str(education.get('college') or ''),
            'degree': str(education.get('degree') or ''),
            'field': str(education.get('branch') or ''),
            'location': '', 'start_date': '',
            'end_date': str(education.get('graduation_year') or ''),
            'details': f"CGPA: {education['cgpa']}" if _nonempty(education.get('cgpa')) else '',
        })

    skills = profile.get('skills') or {}
    for group in SKILL_GROUPS:
        values = skills.get(group) or []
        if isinstance(values, list):
            for index, value in enumerate(values):
                if _nonempty(value):
                    document['skills'].append({'entry_id': f'profile-skill-{group}-{index}', 'source': 'profile',
                                               'name': str(value), 'group': group.replace('_', ' ').title()})

    for section in ('projects', 'experience', 'internships', 'certifications'):
        records = profile.get(section) or []
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            base = {'entry_id': f'profile-{section}-{index}', 'source': 'profile'}
            if section == 'projects':
                technologies = record.get('technologies') or []
                document[section].append(base | {
                    'title': str(record.get('project_name') or ''),
                    'description': str(record.get('description') or ''),
                    'technologies': ', '.join(str(item) for item in technologies if _nonempty(item))
                    if isinstance(technologies, list) else str(technologies), 'link': '',
                })
            elif section in {'experience', 'internships'}:
                technologies = record.get('technologies') or []
                description = ', '.join(str(item) for item in technologies if _nonempty(item)) \
                    if isinstance(technologies, list) else str(technologies)
                document[section].append(base | {
                    'organization': str(record.get('company') or ''), 'role': str(record.get('role') or ''),
                    'location': '', 'start_date': '', 'end_date': str(record.get('duration') or ''),
                    'description': description,
                })
            else:
                document[section].append(base | {
                    'name': str(record.get('name') or ''), 'issuer': str(record.get('issuer') or ''),
                    'date': str(record.get('year') or ''),
                })

    achievements = profile.get('achievements') or {}
    if isinstance(achievements, dict):
        for group, values in achievements.items():
            if isinstance(values, list):
                for index, value in enumerate(values):
                    if _nonempty(value):
                        document['achievements'].append({
                            'entry_id': f'profile-achievement-{group}-{index}', 'source': 'profile',
                            'title': str(value), 'description': group.replace('_', ' ').title(),
                        })
    return document


def _check_profile_sources(document, imported):
    if document.summary_source != 'student':
        raise ResumeBuilderInvalid('The summary must be entered by the student.')
    for field, source in document.personal_sources.items():
        if source == 'profile' and document.personal.model_dump()[field] != imported['personal'][field]:
            raise ResumeBuilderInvalid('Imported contact fields must match the current saved profile.')
    for section in ('education', 'skills', 'projects', 'experience', 'internships', 'certifications', 'achievements'):
        allowed = {item['entry_id']: item for item in imported[section]}
        for item in getattr(document, section):
            if item.source == 'profile':
                expected = allowed.get(item.entry_id)
                if expected is None or item.model_dump(mode='json') != expected:
                    raise ResumeBuilderInvalid('Imported entries must match the current saved profile.')


def _flatten(value):
    return ' '.join(str(value or '').split())


def _entry_lines(section, item):
    if section == 'education':
        title = ' · '.join(part for part in (item.degree, item.field) if part)
        meta = ' · '.join(part for part in (item.institution, item.location,
                                            ' – '.join(part for part in (item.start_date, item.end_date) if part)) if part)
        return [line for line in (title, meta, item.details) if _flatten(line)]
    if section == 'skills':
        return [f"{item.group}: {item.name}" if item.group else item.name]
    if section == 'projects':
        lines = [item.title]
        lines.extend([item.description, f'Technologies: {item.technologies}' if item.technologies else '', item.link])
        return [line for line in lines if _flatten(line)]
    if section in {'experience', 'internships'}:
        heading = ' · '.join(part for part in (item.role, item.organization) if part)
        dates = ' – '.join(part for part in (item.start_date, item.end_date) if part)
        meta = ' · '.join(part for part in (item.location, dates) if part)
        return [line for line in (heading, meta, item.description) if _flatten(line)]
    if section == 'certifications':
        return [' · '.join(part for part in (item.name, item.issuer, item.date) if part)]
    if section == 'achievements':
        return [line for line in (item.title, item.description) if _flatten(line)]
    return []


def resume_text_blocks(document):
    """Return ordered (kind, text) blocks; empty sections are not exported."""
    doc = ResumeDocument.model_validate(document)
    personal = doc.personal
    blocks = []
    if _flatten(personal.name):
        blocks.append(('name', personal.name))
    contacts = [getattr(personal, field) for field in ('email', 'phone', 'location', 'linkedin', 'github', 'portfolio')
                if _flatten(getattr(personal, field))]
    if contacts:
        blocks.append(('contact', '  |  '.join(contacts)))
    section_titles = {'summary': 'Professional Summary', 'education': 'Education', 'skills': 'Skills',
                      'projects': 'Projects', 'experience': 'Work Experience', 'internships': 'Internships',
                      'certifications': 'Certifications', 'achievements': 'Achievements'}
    for section in doc.section_order:
        if section not in doc.visible_sections:
            continue
        if section == 'summary':
            values = [doc.summary] if _flatten(doc.summary) else []
        else:
            values = [line for item in getattr(doc, section) for line in _entry_lines(section, item)
                      if _flatten(line)]
        if values:
            blocks.append(('section', section_titles[section]))
            blocks.extend(('body', value) for value in values)
    return doc, blocks


def _pdf_text(value):
    encoded = _flatten(value).encode('cp1252', errors='replace').decode('cp1252')
    return encoded.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


_GLYPH_WIDTHS = dict(zip(
    ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~',
    [278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,
     556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,
     667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,
     722,667,611,722,667,944,667,667,611,333,278,333,584,556,278,556,556,
     500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,
     278,556,500,722,500,500,500,334,260,334,584],
))


def _measure(value, size):
    safe = _flatten(value).encode('cp1252', errors='replace').decode('cp1252')
    return sum(_GLYPH_WIDTHS.get(char, 1000) for char in safe) * size / 1000


def _wrap(value, max_width, size):
    lines, line = [], ''
    for word in _flatten(value).split(' '):
        if line and _measure(f'{line} {word}', size) <= max_width:
            line = f'{line} {word}'
            continue
        if line:
            lines.append(line)
            line = ''
        fragment = ''
        for char in word:
            if fragment and _measure(fragment + char, size) > max_width:
                lines.append(fragment)
                fragment = char
            else:
                fragment += char
        line = fragment
    if line:
        lines.append(line)
    return lines or ['']


def make_resume_pdf(document):
    """Generate a real, selectable-text PDF with bounded wrapping and pagination."""
    doc, blocks = resume_text_blocks(document)
    modern = doc.template == 'modern'
    regular_font = 'F1'
    bold_font = 'F2'
    pages, commands, y = [], [], 738

    def new_page(continuation=False):
        nonlocal commands, y
        if commands:
            pages.append('\n'.join(commands).encode('cp1252', errors='replace'))
        commands = []
        y = 738
        if continuation:
            label = doc.personal.name or 'Resume'
            commands.append(f'BT /F1 9 Tf 0.38 0.42 0.48 rg 54 {y} Td ({_pdf_text(label)}) Tj ET')
            y -= 25

    def text_line(value, font, size, color, indent=0, x=None):
        nonlocal y
        if y < 58:
            new_page(True)
        safe = _pdf_text(value)
        commands.append(f'BT /{font} {size} Tf {color[0]} {color[1]} {color[2]} rg '
                        f'{x if x is not None else 54 + indent} {y} Td ({safe}) Tj ET')
        y -= 14 if size >= 10 else 12

    for kind, value in blocks:
        limit = 88 if modern else 90
        if kind == 'name':
            size = 21 if modern else 22
            for line in _wrap(value, 504, size):
                x = 54 if modern else 306 - _measure(line, size) / 2
                text_line(line, bold_font, size, ('0.08', '0.16', '0.28'), 0, x)
            commands.append(f'0.12 0.42 0.58 RG 54 {y + 5} m 558 {y + 5} l S')
            y -= 5
        elif kind == 'contact':
            for line in _wrap(value, 504, 9):
                text_line(line, regular_font, 9, ('0.25', '0.29', '0.34'))
            y -= 6
        elif kind == 'section':
            if y < 82:
                new_page(True)
            y -= 7
            text_line(value.upper() if not modern else value, bold_font, 11, ('0.09', '0.25', '0.38'))
            commands.append(f'0.75 0.79 0.83 RG 54 {y + 7} m 558 {y + 7} l S')
            y -= 4
        else:
            for line in _wrap(value, 500, 10):
                text_line(line, regular_font, 10, ('0.13', '0.15', '0.18'), 4)
            y -= 2
    if commands or not pages:
        pages.append('\n'.join(commands).encode('cp1252', errors='replace'))

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        None,
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>',
    ]
    page_ids = []
    for stream in pages:
        content_id = len(objects) + 1
        objects.append(b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n' + stream + b'\nendstream')
        page_id = len(objects) + 1
        page_ids.append(page_id)
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                       f'/Resources << /Font << /F1 {3 if modern else 5} 0 R /F2 {4 if modern else 6} 0 R >> >> '
                       f'/Contents {content_id} 0 R >>'.encode('ascii'))
    kids = ' '.join(f'{page_id} 0 R' for page_id in page_ids)
    objects[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode('ascii')

    output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f'{number} 0 obj\n'.encode('ascii'))
        output.extend(body)
        output.extend(b'\nendobj\n')
    xref_offset = len(output)
    output.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    output.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    output.extend(f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
                  f'startxref\n{xref_offset}\n%%EOF\n'.encode('ascii'))
    return bytes(output)


class ResumeBuilderService:
    def __init__(self, profiles, store=None, clock=None):
        self.profiles = profiles
        self.store = store or ResumeBuilderStore()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _owned_profile(self, identity, profile_id):
        profile, _ = self.profiles.get(identity, profile_id)
        return profile

    def authorize_profile(self, identity, profile_id):
        self._owned_profile(identity, profile_id)

    def get_draft(self, identity, profile_id):
        self._owned_profile(identity, profile_id)
        row = self.store.get(identity, profile_id)
        if row is None:
            return {'draft': empty_document(), 'updated_at': None, 'has_saved_draft': False}
        try:
            document = ResumeDocument.model_validate_json(row['document_json']).model_dump(mode='json')
        except Exception:
            raise ResumeBuilderInvalid('Saved resume draft is unavailable. Contact support if the issue continues.') from None
        document['revision'] = row['revision']
        return {'draft': document, 'updated_at': row['updated_at'], 'has_saved_draft': True}

    def import_profile(self, identity, profile_id):
        profile = self._owned_profile(identity, profile_id)
        if profile.get('verified') is not True:
            raise ResumeBuilderConflict('Confirm this profile before importing its information.')
        return {'content': import_profile_document(profile), 'profile_revision': profile.get('revision')}

    def save(self, identity, profile_id, values):
        profile = self._owned_profile(identity, profile_id)
        document = ResumeDocument.model_validate(values)
        _check_profile_sources(document, import_profile_document(profile))
        encoded = json.dumps(document.model_dump(mode='json'), ensure_ascii=True, allow_nan=False,
                             separators=(',', ':'))
        if len(encoded.encode('utf-8')) > 1024 * 1024:
            raise ResumeBuilderInvalid('Resume draft is too large.')
        saved = self.store.save(identity, profile_id, document.revision, encoded, self.clock().isoformat())
        if saved is None:
            raise ResumeBuilderConflict('This resume changed in another session. Reload it before saving again.')
        result = ResumeDocument.model_validate_json(saved['document_json']).model_dump(mode='json')
        result['revision'] = saved['revision']
        return {'draft': result, 'updated_at': saved['updated_at'], 'has_saved_draft': True}

    def export_pdf(self, identity, profile_id):
        response = self.get_draft(identity, profile_id)
        if not response['has_saved_draft']:
            raise ResumeBuilderConflict('Save your resume before exporting the PDF.')
        _, blocks = resume_text_blocks(response['draft'])
        if not blocks:
            raise ResumeBuilderConflict('Add at least one resume section before exporting the PDF.')
        return make_resume_pdf(response['draft'])
