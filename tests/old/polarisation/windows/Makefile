NAME:=test.exe
HEADER_DIR:="C:\Program Files (x86)\IVI Foundation\VISA\WinNT\Include"
VISA_LIB:="C:\Program Files (x86)\IVI Foundation\VISA\WinNT\Lib_x64\msc\visa64.lib"
TLPAX_LIB="C:\Program Files (x86)\IVI Foundation\VISA\WinNT\Lib_x64\msc\TLPAX_64.lib"

all:
	cl sample.c /Fe:$(NAME) $(VISA_LIB) $(TLPAX_LIB) /I $(HEADER_DIR)

