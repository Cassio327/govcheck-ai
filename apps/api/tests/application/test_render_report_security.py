import pytest

from govcheck.application.render_report import _markdown_text


@pytest.mark.parametrize(
    ("untrusted", "expected"),
    [
        ("<script>alert('x')</script>", "&lt;script&gt;alert\\('x'\\)&lt;/script&gt;"),
        ("# Título", "\\# Título"),
        ("[clique](javascript:alert(1))", "\\[clique\\]\\(javascript:alert\\(1\\)\\)"),
        ("Linha 1\n# instrução", "Linha 1 \\# instrução"),
    ],
)
def test_markdown_report_treats_untrusted_values_as_text(untrusted, expected) -> None:
    assert _markdown_text(untrusted) == expected
