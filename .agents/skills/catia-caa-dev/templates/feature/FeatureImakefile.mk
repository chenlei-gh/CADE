# COPYRIGHT DASSAULT SYSTEMES 2026
# Imakefile.mk for Feature Module

# Module name (should match your feature class prefix without framework prefix)
# Example: If class is CAASmpMyFeature, use CAASmpMyFeature
# Example: If class is MyFeature in MyFramework, use MyFeature
MODULE_NAME = {PREFIX}{FEATURE_NAME}

# Built objects - source files to compile
BUILT_OBJECTS = \
    $(MODULE_NAME).cpp \
    $(MODULE_NAME)Build.cpp \
    $(MODULE_NAME)Replace.cpp

# Alternative if using single implementation file:
# BUILT_OBJECTS = $(MODULE_NAME).cpp

#=============================================================================
# LINK WITH
#=============================================================================
# Frameworks to link against
# Add all frameworks your code uses interfaces from

# Core CAA frameworks (always required for features)
LINK_WITH = \
    System \
    ObjectModelerBase \
    MechanicalModeler

# Additional frameworks (uncomment as needed)
# Geometric and topological frameworks
# LINK_WITH += GeometricObjects
# LINK_WITH += TopologicalObjects
# LINK_WITH += NewTopologicalObjects

# Math framework
# LINK_WITH += Mathematics

# Visualization frameworks
# LINK_WITH += Visualization
# LINK_WITH += VisualizationBase

# Dialog frameworks (if creating UI)
# LINK_WITH += Dialog
# LINK_WITH += DI0PANV2

# Sketcher framework (if using sketches)
# LINK_WITH += Sketcher

# Knowledge frameworks (if using parameters/formulas)
# LINK_WITH += KnowledgeInterfaces
# LINK_WITH += LiteralFeatures

#=============================================================================
# COMPILATION FLAGS
#=============================================================================
# Uncomment to enable specific compilation options

# Enable debugging symbols
# CXXFLAGS += -g

# Enable all warnings
# CXXFLAGS += -Wall

# Treat warnings as errors (use with caution)
# CXXFLAGS += -Werror

# Optimization level
# CXXFLAGS += -O2

#=============================================================================
# PREPROCESSOR DEFINITIONS
#=============================================================================
# Define preprocessor macros if needed

# Define module export/import macro (for Windows DLL)
# CPPFLAGS += -D{FRAMEWORK_NAME}_EXPORTS

# Define feature-specific flags
# CPPFLAGS += -DUSE_ADVANCED_GEOMETRY

#=============================================================================
# INCLUDE PATHS
#=============================================================================
# Additional include directories (beyond automatic framework includes)
# Usually not needed as framework includes are automatic

# Example: Include local headers from another module
# INCLUDES += -I$(MkmkBIN_PATH)/../LocalInterfaces

# Example: Include third-party headers
# INCLUDES += -I/usr/local/include/thirdparty

#=============================================================================
# RESOURCE FILES
#=============================================================================
# NLS resource files (optional)
# Placed in CNext/resources/msgcatalog/

# Feature display names and descriptions
# Resource file: $(MODULE_NAME).CATNls

# Error messages
# Resource file: $(MODULE_NAME)Errors.CATNls

#=============================================================================
# STARTUP CATALOG
#=============================================================================
# Feature StartUp catalog file
# Placed in CNext/resources/graphic/

# Catalog file: {FRAMEWORK_NAME}.CATfct
# Created by StartUpCatalog.cpp functions

#=============================================================================
# DICTIONARY ENTRIES
#=============================================================================
# Update {FRAMEWORK_NAME}.dic with interface implementations:
#
# $(MODULE_NAME)  CATIBuild                lib{FRAMEWORK_NAME}
# $(MODULE_NAME)  CATIReplace              lib{FRAMEWORK_NAME}
# $(MODULE_NAME)  CATIMmiMechanicalFeature lib{FRAMEWORK_NAME}
# $(MODULE_NAME)  CATIMmiResultFeature     lib{FRAMEWORK_NAME}

#=============================================================================
# BUILD TARGETS
#=============================================================================
# Default target builds shared library
# Run: mkmk -u or mkmk -a

# Standard CAA build process will create:
# - On Windows: lib{FRAMEWORK_NAME}.dll
# - On Unix:    lib{FRAMEWORK_NAME}.so

#=============================================================================
# SPECIAL BUILD RULES
#=============================================================================
# Add custom build rules if needed

# Example: Generate code from template
# $(MODULE_NAME)Generated.cpp: $(MODULE_NAME).template
# 	generate_code.sh $< > $@

# Example: Copy resources during build
# resources: $(MODULE_NAME).CATNls
# 	cp $< $(MkmkBIN_PATH)/../resources/msgcatalog/

#=============================================================================
# DEPENDENCIES
#=============================================================================
# Automatic dependency generation is handled by mkmk
# Manual dependencies only needed for special cases

# Example: Feature depends on generated header
# $(MODULE_NAME).o: GeneratedHeader.h

#=============================================================================
# NOTES
#=============================================================================
# 1. File naming convention:
#    - Imakefile.mk must be in module directory
#    - Module directory name can differ from MODULE_NAME
#    - Source files should use MODULE_NAME prefix
#
# 2. Build commands:
#    - mkmk -u: Update makefiles and build changed files
#    - mkmk -a: Rebuild all files
#    - mkrun: Run CATIA with your framework loaded
#    - mkCheckSource: Check source file consistency
#
# 3. Framework structure:
#    YourFramework.m/
#    +-- src/
#    |   +-- FeatureModule.m/
#    |       +-- Imakefile.mk (this file)
#    |       +-- {PREFIX}{FEATURE_NAME}.h
#    |       +-- {PREFIX}{FEATURE_NAME}.cpp
#    |       +-- {PREFIX}{FEATURE_NAME}Build.cpp
#    |       +-- {PREFIX}{FEATURE_NAME}Replace.cpp
#    +-- LocalInterfaces/
#    +-- ProtectedInterfaces/
#    +-- PublicInterfaces/
#
# 4. Common build issues:
#    - Missing framework in LINK_WITH
#    - Incorrect interface TIE declarations
#    - Missing Dictionary entries
#    - Wrong module name
