# COPYRIGHT DASSAULT SYSTEMES YYYY
#
# Imakefile.mk for ModuleName
#

# Module name
MODULE = ModuleName

# Source files
SOURCES = \
    src/IInterfaceName.cpp \
    src/ComponentName.cpp

# Local headers
LOCAL_HEADERS = \
    LocalInterfaces/ComponentName.h

# Public headers (interfaces)
PUBLIC_HEADERS = \
    PublicInterfaces/IInterfaceName.h

# Dependencies
LINK_WITH = \
    System \
    ObjectModelerBase
MkmkUnauthorizedAPI_Check = FALSE
