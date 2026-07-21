"""The test the whole project exists for (§ 13.2).

Generate a PDF, read it back with pypdf, and check MediaBox and mark
coordinates against expected values — to 1 µm. Golden comparisons check parsed
geometry, never bytes, so a reportlab update cannot break the suite.

M1 acceptance criterion 2 (§ 14) is exactly this test passing for
`millimeter-a4`: MediaBox 210 x 297 mm, line spacing 1.000 mm, every fifth line
emphasised.
"""

import pytest

pytest.skip(
    "Not implemented yet — arrives with M1 (§ 14). This file exists so the "
    "dedicated CI job fails loudly if it is ever removed.",
    allow_module_level=True,
)
