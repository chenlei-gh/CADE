// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "ClassName.h"
#include <iostream>
using namespace std;

ClassName::ClassName() : _data(0)
{
    cout << "ClassName::ClassName" << endl;
}

ClassName::~ClassName()
{
    cout << "ClassName::~ClassName" << endl;
}

int ClassName::MethodName(int iParam)
{
    cout << "ClassName::MethodName(" << iParam << ")" << endl;
    _data = iParam;
    return _data;
}
