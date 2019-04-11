import mistune
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import html


class HighlightRenderer(mistune.Renderer):
    def block_code(self, code, lang):
        if not lang:
            escaped = mistune.escape(code)
            return f"\n<pre><code>{escaped}</code></pre>\n"

        lexer = get_lexer_by_name(lang, stripall=True)
        formatter = html.HtmlFormatter()
        return highlight(code, lexer, formatter)


class PlaintextRenderer(mistune.Renderer):
    def _nothing(*args, **kwargs):
        return " "

    def paragraph(self, text):
        return f"{text}\n"

    block_code = (
        block_quote
    ) = (
        block_html
    ) = header = hrule = list = list_item = table = table_row = table_cell = _nothing

    def autolink(self, link, is_email):
        return link

    # def codespan(self, text):
    #     return f"`{text}`"

    # def double_emphasis(self, text):
    #     return f"**{text}**"

    # def emphasis(self, text):
    #     return f"*{text}*"

    linebreak = newline = image = _nothing

    def link(self, link, title, text):
        return f"[{link}]"

    def strikethrough(self, text):
        return text


highlight_renderer = HighlightRenderer(escape=True)
plaintext_renderer = PlaintextRenderer(escape=True)

highlight_markdown = mistune.Markdown(renderer=highlight_renderer)
plaintext_markdown = mistune.Markdown(renderer=plaintext_renderer)
