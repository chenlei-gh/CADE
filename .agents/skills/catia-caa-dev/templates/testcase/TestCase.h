// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef TestCaseName_h
#define TestCaseName_h

// System Framework
#include "CATTestCase.h"

/**
 * @brief TestCaseName - CAA unit test case
 */
class TestCaseName : public CATTestCase
{
public:
    TestCaseName();
    virtual ~TestCaseName();

    virtual void SetUp();
    virtual void TearDown();

    void TestMethod1();
    void TestMethod2();
    void TestMethod3();

private:
    TestCaseName(const TestCaseName&);
    TestCaseName& operator=(const TestCaseName&);
};

#endif
