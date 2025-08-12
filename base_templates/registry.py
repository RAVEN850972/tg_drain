from .base1 import BaseTemplate1
from .base2 import BaseTemplate2
from .base3 import BaseTemplate3
from .base4 import BaseTemplate4
from .base5 import BaseTemplate5
from .base6 import BaseTemplate6  

BASE_TEMPLATES = [
    BaseTemplate1, BaseTemplate2, BaseTemplate3,
    BaseTemplate4, BaseTemplate5, BaseTemplate6  
]
BASE_TEMPLATES_MAP = {tpl.id: tpl for tpl in BASE_TEMPLATES}