# QCTools
## Installation

Go into the project folder and type:
```
python setup.py install
```
If you're feeling frisky
```
python setup.py develop
```
installs in develop mode and the project folder is where the module
lives. Any editing done will immediately carry over.


## Usage
Requires QCodes for obvious reasons. 
To make all functions available, run:
```python
import imp
import qctools as qct
from qctools.db_extraction import db_extractor
from qctools.doNd import do1d,do1d_settle,do2d,do2d_settle
```