// COPYRIGHT DASSAULT SYSTEMES YYYY

#include "TestCaseName.h"
#include "CATAssert.h"
#include <iostream>
using namespace std;

// Test Suite Registration
CATBeginTestSuite(TestCaseName)
    CATAddTest(TestMethod1)
    CATAddTest(TestMethod2)
    CATAddTest(TestMethod3)
CATEndTestSuite(TestCaseName)

TestCaseName::TestCaseName() : CATTestCase("TestCaseName")
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

void TestCaseName::TestMethod1()
{
    cout << "TestCaseName::TestMethod1" << endl;
    int expected = 10;
    int actual = 5 + 5;
    CATAssertEquals(expected, actual, "Addition test failed");
}

void TestCaseName::TestMethod2()
{
    cout << "TestCaseName::TestMethod2" << endl;
    CATAssertTrue(TRUE, "Should pass");
}

void TestCaseName::TestMethod3()
{
    cout << "TestCaseName::TestMethod3" << endl;
    CATAssertNotNull(this, "Object should not be null");
}
