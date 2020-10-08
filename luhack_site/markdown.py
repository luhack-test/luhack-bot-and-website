import mistune
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound
from pygments.formatters import html


class HighlightRenderer(mistune.HTMLRenderer):
    def block_code(self, code, lang):
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

    def link(self, link, title, text):
        return f"[{link}]"

    def strikethrough(self, text):
        return text


highlight_renderer = HighlightRenderer(escape=True)
highlight_renderer_unsafe = HighlightRenderer(escape=False)
plaintext_renderer = PlaintextRenderer(escape=True)

highlight_markdown = mistune.create_markdown(renderer=highlight_renderer, plugins=['url'])
highlight_markdown_unsafe = mistune.create_markdown(renderer=highlight_renderer_unsafe, plugins=['url'])
plaintext_markdown = mistune.create_markdown(renderer=plaintext_renderer, plugins=['url'])
