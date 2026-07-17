// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "TestCaseName.h"
#include "CATAssert.h"
#include <iostream>
using namespace std;

TestCaseName::TestCaseName()
{
    cout << "TestCaseName::TestCaseName" << endl;
}

TestCaseName::~TestCaseName()
{
    cout << "TestCaseName::~TestCaseName" << endl;
}

void TestCaseName::SetUp()
{
    cout << "TestCaseName::SetUp" << endl;
}

void TestCaseName::TearDown()
{
    cout << "TestCaseName::TearDown" << endl;
}

void TestCaseName::RunAll()
{
    SetUp();
    TestMethod1();
    TestMethod2();
    TestMethod3();
    TearDown();
}

void TestCaseName::TestMethod1()
{
    cout << "TestCaseName::TestMethod1" << endl;
    int expected = 10;
    int actual = 5 + 5;
    CATAssert(expected == actual);
}

void TestCaseName::TestMethod2()
{
    cout << "TestCaseName::TestMethod2" << endl;
    CATAssert(1);
}

void TestCaseName::TestMethod3()
{
    cout << "TestCaseName::TestMethod3" << endl;
    CATAssert(this != NULL);
}
