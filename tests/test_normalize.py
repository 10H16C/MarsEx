from entity_resolver.steps.normalize import compact, normalize


def test_normalize_casefolds_and_collapses_whitespace() -> None:
    assert normalize("  Microsoft \t SharePoint\n") == "microsoft sharepoint"


def test_normalize_preserves_punctuation() -> None:
    assert normalize("Node.js / C++") == "node.js / c++"


def test_compact_removes_spaces_only() -> None:
    assert compact(normalize("AWS  EKS-1")) == "awseks-1"
