#ifndef %PROJ_PREFIX_UPPER%_%LIB_NAME_UPPER%_EXPORTS_
#define %PROJ_PREFIX_UPPER%_%LIB_NAME_UPPER%_EXPORTS_

#if defined(_MSC_VER) || defined(__CYGWIN__) || defined(__MINGW32__) || defined( __BCPLUSPLUS__)  || defined( __MWERKS__)
    #  if defined( %PROJ_PREFIX_UPPER%_LIB_STATIC )
    #    define %PROJ_PREFIX_UPPER%%LIB_NAME_UPPER%_EXPORT
    #  elif defined( %PROJ_PREFIX_UPPER%_%LIB_NAME_UPPER%_LIB )
    #    define %PROJ_PREFIX_UPPER%%LIB_NAME_UPPER%_EXPORT   __declspec(dllexport)
    #  else
    #    define %PROJ_PREFIX_UPPER%%LIB_NAME_UPPER%_EXPORT   __declspec(dllimport)
    #  endif
#else
    #  define %PROJ_PREFIX_UPPER%%LIB_NAME_UPPER%_EXPORT
#endif

//#if defined(_MSC_VER)
//	#pragma warning(disable : 4514)
//	#pragma warning(disable : 4251)
//#endif

//#include <memory>
//#include <set>
//#include <string>
//#include <sstream>
//#include <vector>
//#include <map>
//#include <iostream>

#endif
