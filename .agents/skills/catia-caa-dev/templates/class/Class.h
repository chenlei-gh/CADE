// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef ClassName_h
#define ClassName_h

/**
 * @brief ClassName - Plain C++ utility class
 * 
 * Standard C++ class (not a CAA component).
 * Use for utilities, helpers, data structures, managers.
 * 
 * Does NOT inherit from CATBaseUnknown.
 */
class ClassName
{
public:
    ClassName();
    virtual ~ClassName();

    int MethodName(int iParam);

private:
    int _data;

    ClassName(const ClassName&);
    ClassName& operator=(const ClassName&);
};

#endif
