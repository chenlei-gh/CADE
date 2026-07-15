# COPYRIGHT DASSAULT SYSTEMES 2026
# Imakefile for Dialog module

BUILT_OBJECT_TYPE=SHARED LIBRARY

# Link with required CAA frameworks
LINK_WITH=JS0GROUP JS0CORBA JS0FM
LINK_WITH=$(LINK_WITH) ApplicationFrame Dialog Visualization

# Additional compiler flags (optional)
LOCAL_CCFLAGS=/EHsc

# Additional linker flags (optional)
LOCAL_LNKFLAGS=
