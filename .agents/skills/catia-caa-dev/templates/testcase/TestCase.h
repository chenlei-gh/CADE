// COPYRIGHT DASSAULT SYSTEMES YYYY
#ifndef TestCaseName_h
#define TestCaseName_h

/**
 * @brief TestCaseName - CAA test fixture
 *
 * B28 does not expose a CATTestCase framework. This fixture deliberately
 * uses only public C++ methods; assertions are implemented with CATAssert.
 */
class TestCaseName
{
public:
    TestCaseName();
    ~TestCaseName();

    void SetUp();
    void TearDown();

    void RunAll();
    void TestMethod1();
    void TestMethod2();
    void TestMethod3();

private:
    TestCaseName(const TestCaseName&);
    TestCaseName& operator=(const TestCaseName&);
};

#endif
