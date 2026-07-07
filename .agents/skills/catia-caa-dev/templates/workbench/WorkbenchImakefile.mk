#=======================================================================
# COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
#=======================================================================
# {{PREFIX}}Workbench - Workbench module build configuration
#=======================================================================

# Shared library generation (BOA pattern)
BUILT_OBJECT_TYPE = LOAD MODULE

# Source files to compile
LINK_WITH = \
    {{PREFIX}}Workbench \
    {{PREFIX}}Addin

# Required framework dependencies
# Application Frame (mandatory for workbench/addin)
LINK_WITH += \
    CATApplicationFrame

# Dialog and Visualization (if UI commands are included)
LINK_WITH += \
    CATDialog \
    CATViz

# Add product-specific frameworks as needed
# Example for Part Design integration:
# LINK_WITH += \
#     CATPrtInterfaces \
#     CATMecModInterfaces

# Example for Assembly Design:
# LINK_WITH += \
#     CATAsmInterfaces

# System and base frameworks
LINK_WITH += \
    CATObjectModelerBase \
    CATSystem

# Resource files to copy (NLS and RSC)
# These define toolbar layout, icons, and localized strings
BUILT_OBJECT_ASSOCIATED_FILES = \
    CNext/resources/msgcatalog/{{PREFIX}}Workbench.CATNls \
    CNext/resources/msgcatalog/{{PREFIX}}Workbench_Chinese.CATNls \
    CNext/resources/msgcatalog/{{PREFIX}}Workbench.CATRsc

# Icon resources (if icons are provided)
# BUILT_OBJECT_ASSOCIATED_FILES += \
#     CNext/resources/graphic/icons/normal/{{PREFIX}}Icon.png

#=======================================================================
# Include standard build rules
#=======================================================================
include $(MkmkRoot)/libso.mk
