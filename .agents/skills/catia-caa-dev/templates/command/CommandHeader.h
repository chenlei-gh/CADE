// COPYRIGHT DASSAULT SYSTEMES YYYY
#include "<CommandHeaderName>.h"
#include "<CommandClassName>.h"

<CommandHeaderName>::<CommandHeaderName>(const CATString &iHeaderName)
    : CATCommandHeader(iHeaderName)
    , _commandName("<CommandClassName>")
    , _iconPath("Icons/<CommandClassName>.bmp")
{
}

<CommandHeaderName>::~<CommandHeaderName>()
{
}

CATCommandHeader *<CommandHeaderName>::Clone() const
{
    return new <CommandHeaderName>(GetName());
}

CATUnicodeString <CommandHeaderName>::GetCommandName() const
{
    return _commandName;
}

CATUnicodeString <CommandHeaderName>::GetIconPath() const
{
    return _iconPath;
}
