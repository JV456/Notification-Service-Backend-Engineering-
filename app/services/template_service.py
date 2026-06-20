import re
from typing import Any, Dict, Optional

# Matches {{name}}, {{ order_id }}, etc.
VAR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(text: Optional[str], variables: Dict[str, Any]) -> Optional[str]:
    """
    Replace {{key}} placeholders in `text` with values from `variables`.
    Unknown placeholders are left as-is (rather than raising), so a missing
    variable doesn't take down the whole send — it just shows up visibly in
    the rendered message for easy debugging.
    """
    if text is None:
        return None

    def replace(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key in variables:
            return str(variables[key])
        return match.group(0)

    return VAR_PATTERN.sub(replace, text)
