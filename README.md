# QCTools
## Installation

Go into the project folder and type:
```
pip install {path to package}
```
For an editable install (recommended for easy repository updates):
```
pip install -e {path to package}
```
Now, the project folder is where the module lives. 
Any editing done will immediately carry over.


## Usage
Requires QCodes for obvious reasons. 
To make all functions available, run:
```python
import imp
import qctools as qct
from qctools.db_extraction import db_extractor
from qctools.doNd import doNd
```