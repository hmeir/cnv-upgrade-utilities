from utils.models import ReleasedBuild


class TestReleasedBuildSkipsCoercion:
    """API sometimes returns skips as "" instead of []."""

    def test_empty_string_coerced_to_empty_list(self):
        build = ReleasedBuild(csv_version="v4.16.36", version="v4.16.36.rhel9-1", skips="")
        assert build.skips == []

    def test_none_uses_default_empty_list(self):
        build = ReleasedBuild(csv_version="v4.16.36", version="v4.16.36.rhel9-1", skips=None)
        assert build.skips == []

    def test_comma_separated_string_coerced_to_list(self):
        build = ReleasedBuild(csv_version="v4.16.36", version="v4.16.36.rhel9-1", skips="v4.16.34,v4.16.35")
        assert build.skips == ["v4.16.34", "v4.16.35"]

    def test_list_input_unchanged(self):
        build = ReleasedBuild(csv_version="v4.16.36", version="v4.16.36.rhel9-1", skips=["v4.16.34"])
        assert build.skips == ["v4.16.34"]

    def test_missing_field_uses_default(self):
        build = ReleasedBuild(csv_version="v4.16.36", version="v4.16.36.rhel9-1")
        assert build.skips == []
