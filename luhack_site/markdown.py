import textwrap
from functools import wraps

import mistune
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound
from pygments.formatters import html


AUDIO_PATTERN = (
    r'!audio\['
    r'([\S]*?)\]\(([\S]+?)\)'
)

def parse_audio(inline, m, state):
    title, link = m.group(1), m.group(2)
    return 'audio', link, title

def render_html_audio(link, title):
    return f'<audio controls="controls" src="{link}">{title}</audio>'

VIDEO_PATTERN = (
    r'!video\['
    r'([\S]*?)\]\(([\S]+?)\)'
)

def parse_video(inline, m, state):
    title, link = m.group(1), m.group(2)
    return 'video', link, title

def render_html_video(link, title):
    print('video', link, title)
    return f'<video controls="controls" src="{link}">{title}</video>'

def plugin_media(md):
    md.inline.register_rule('audio', AUDIO_PATTERN, parse_audio)
    md.inline.register_rule('video', VIDEO_PATTERN, parse_video)
    md.inline.rules.append('audio')
    md.inline.rules.append('video')

    if md.renderer.NAME == 'html':
        md.renderer.register('audio', render_html_audio)
        md.renderer.register('video', render_html_video)

class HighlightRenderer(mistune.HTMLRenderer):
    def block_code(self, code, lang=None):
        def no_highlight():
            escaped = mistune.escape(code)
            return f"\n<pre><code>{escaped}</code></pre>\n"

        if not lang:
            return no_highlight()

        try:
            lexer = get_lexer_by_name(lang, stripall=True)
            formatter = html.HtmlFormatter()
            return highlight(code, lexer, formatter)
        except ClassNotFound:
            return no_highlight()

    def image(self, src, alt="", title=None):
        src = self._safe_url(src)
        html = f'<img class="pure-img" src="{src}" alt="{alt}" '

        if title:
            title = mistune.escape_html(title)
            html = f'{html} title="{title}" '

        return f"{html} />"


class PlaintextRenderer(mistune.HTMLRenderer):
    def _nothing(*args, **kwargs):
        return " "

    def paragraph(self, text):
        return f"{text}\n"

    block_code = (
        block_quote
    ) = (
        block_html
    ) = heading = list = list_item = table = table_row = table_cell = _nothing

    linebreak = newline = image = _nothing

    def link(self, link, title="", text=""):
        contents = title or text or link
        return f"[{contents}]"

    def strikethrough(self, text):
        return text


highlight_renderer = HighlightRenderer(escape=True)
highlight_renderer_unsafe = HighlightRenderer(escape=False)
plaintext_renderer = PlaintextRenderer(escape=True)

highlight_markdown = mistune.create_markdown(renderer=highlight_renderer, plugins=['url', 'table', plugin_media])
highlight_markdown_unsafe = mistune.create_markdown(renderer=highlight_renderer_unsafe, plugins=['url', 'table', plugin_media])
length_constrained_plaintext_markdown = mistune.create_markdown(renderer=plaintext_renderer, plugins=['url'])

uncounted_tokens = {"block_code", "block_quote", "block_html", "heading",
                    "list", "list_item", "table", "table_row", "table_cell",
                    "linebreak", "newline", "image"
                    }

def len_limit_hook(self, tokens, state):
    limit = 500
    current = 0
    out = []

    for tok in tokens:
        if tok["type"] in uncounted_tokens:
            continue

        if "text" not in tok:
            continue

        length = len(tok["text"])

        if (current + length) >= limit:
            if tok["type"] in {"paragraph", "text"}:
                tok["text"] = textwrap.shorten(tok["text"], limit - current, placeholder="...")
                out.append(tok)
            else:
                out.append({"type": "text", "text": "..."})
            break

        current += length
        out.append(tok)

    return out

length_constrained_plaintext_markdown.before_render_hooks.append(len_limit_hook)
length_constrained_plaintext_markdown.after_render_hooks.append(lambda s, result, st: result.replace("\n", " "))
