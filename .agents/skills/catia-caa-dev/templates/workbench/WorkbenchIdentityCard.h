// COPYRIGHT DASSAULT SYSTEMES {{YEAR}}
//===================================================================
// {{PREFIX}}IdentityCard.h
// Framework identity card - declares prerequisite frameworks
//===================================================================
// ⚠️ 2026-07 对 B28 全目录核实：原模版的 CATFrmIdentityCard.h 及
// AddHeaderAddin/AddHeaderWorkshop 宏均不存在于 B28，已全部移除。
//
// IdentityCard.h 的真实职责只有一个：声明本框架依赖的其它框架
// （AddPrereqComponent），由 mkCreateIC 生成和维护。
//
// Addin/Workbench 注册不在本文件——在框架的 .dic 字典文件里：
//   {{PREFIX}}Addin      CATIWorkbenchAddin        lib{{PREFIX}}Module
//   {{PREFIX}}Workbench  CATIPrtWksConfiguration   lib{{PREFIX}}Module
// （真实示例：B28 win_b64/code/dictionary/*.dic，如
//  "CATStkPrtWksAddin  CATIWorkbenchAddin  libCATStkUIPrtWkbAddin"）
//===================================================================

// -->Prereq Components Declaration
   AddPrereqComponent("System",Public);
   AddPrereqComponent("ApplicationFrame",Public);
   AddPrereqComponent("DialogEngine",Public);

// 按需追加（目标 workbench 的接口框架），例如：
//   AddPrereqComponent("MecModInterfaces",Public);     // Part Design
//   AddPrereqComponent("ProductStructureInterfaces",Public); // Assembly
