"""test_utils

Tests for utils functions

created 26-jan-2021 by docker@instantlinux.net
"""

import test_base
from apicrud import utils


class TestUtils(test_base.TestBase):

    def test_strip_tags(self):
        # from https://www.w3schools.com/html/tryit.asp?
        # filename=tryhtml_basic_document
        self.assertEqual(utils.strip_tags(
            """<!DOCTYPE html>
<html>
<body>

<h1>My First Heading</h1>

<p>My first paragraph.</p>

</body>
</html>
"""),
            """
 
 

 My First Heading 

 My first paragraph. 

 
 
""")  # noqa
