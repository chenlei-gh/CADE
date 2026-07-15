//===================================================================
// COPYRIGHT DASSAULT SYSTEMES YYYY
//===================================================================
// Imakefile for module ModuleName
//===================================================================

BUILT_OBJECT_TYPE=SHARED LIBRARY

LOCAL_CCFLAGS=/EHsc

#INSERTION ZONE NOT FOUND, MOVE AND APPEND THIS VARIABLE IN YOUR LINK STATEMENT
LINK_WITH = $(WIZARD_LINK_MODULES)
# DO NOT EDIT :: 3DS WIZARDS WILL ADD CODE HERE
WIZARD_LINK_MODULES =  \
JS0GROUP \
JS0FM \
CATApplicationFrame \
CATDialogEngine \
DI0PANV2 
# END WIZARD EDITION ZONE
