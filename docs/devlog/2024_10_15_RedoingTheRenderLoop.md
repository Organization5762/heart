# macOS Render Loop Crash Log

## Problem Statement

Investigate an `NSInternalInconsistencyException` triggered on macOS when the pygame window title updates off the main thread.

## Materials

- macOS workstation running the Heart runtime via `totem`.
- Access to SDL2 and pygame debug symbols.
- Tools for inspecting thread stacks (Console, lldb, or logging).

## Technical Approach

Capture the failing stack trace, confirm that window title changes happen outside the main thread, and evaluate mitigation strategies in the SDL layer or runtime loop.

## Failure Trace

```
2024-10-15 22:49:38.795 Python[56724:1033560] *** Terminating app due to uncaught exception 'NSInternalInconsistencyException', reason: 'NSWindow drag regions should only be invalidated on the Main Thread!'
*** First throw call stack:
(
        0   CoreFoundation                      0x00007ff81580743b __exceptionPreprocess + 242
        1   libobjc.A.dylib                     0x00007ff815356e25 objc_exception_throw + 48
        2   CoreFoundation                      0x00007ff81582f5d6 _CFBundleGetValueForInfoKey + 0
        3   AppKit                              0x00007ff8188d6161 -[NSWindow(NSWindow_Theme) _postWindowNeedsToResetDragMarginsUnlessPostingDisabled] + 307
        4   AppKit                              0x00007ff8188e3931 -[NSThemeFrame _tileTitlebarAndRedisplay:] + 111
        5   AppKit                              0x00007ff8188f4b77 -[NSTitledFrame _titleDidChange] + 158
        6   AppKit                              0x00007ff81916da6e -[NSTitledFrame setTitle:subtitle:] + 690
        7   AppKit                              0x00007ff8188f47aa -[NSThemeFrame setTitle:] + 50
        8   AppKit                              0x00007ff818e8b38e -[NSFrameView _updateTitleProperties:animated:] + 51
        9   AppKit                              0x00007ff819160679 -[NSThemeFrame _updateTitleProperties:animated:] + 186
        10  CoreFoundation                      0x00007ff815784424 __CFNOTIFICATIONCENTER_IS_CALLING_OUT_TO_AN_OBSERVER__ + 137
        11  CoreFoundation                      0x00007ff81581e45a ___CFXRegistrationPost_block_invoke + 88
        12  CoreFoundation                      0x00007ff81581e3a9 _CFXRegistrationPost + 536
        13  CoreFoundation                      0x00007ff815757969 _CFXNotificationPost + 735
        14  Foundation                          0x00007ff81658ff2c -[NSNotificationCenter postNotificationName:object:userInfo:] + 82
        15  AppKit                              0x00007ff819041b1a -[NSWindowTitleController _propertiesChanged:] + 147
        16  AppKit                              0x00007ff8188f4592 -[NSWindow _dosetTitle:andDefeatWrap:] + 220
        17  libSDL2-2.0.0.dylib                 0x000000010eea4c6f Cocoa_SetWindowTitle + 127
        18  display.cpython-313-darwin.so       0x000000010c34ccdc pg_set_caption + 172
        19  Python                              0x000000010a6eaac5 cfunction_call + 70
        20  Python                              0x000000010a7b5c47 _PyObject_MakeTpCall + 131
        21  Python                              0x000000010a5aa3cf _PyEval_EvalFrameDefault + 11126
        22  Python                              0x000000010a7f3759 method_vectorcall.llvm.7217328468435865199 + 219
        23  Python                              0x000000010a5ab528 _PyEval_EvalFrameDefault + 15567
        24  Python                              0x000000010a7f3854 method_vectorcall.llvm.7217328468435865199 + 470
        25  Python                              0x000000010a5f03ea thread_run + 133
        26  Python                              0x000000010a55ff08 pythread_wrapper.llvm.988343010916623 + 43
        27  libsystem_pthread.dylib             0x00007ff8156b4259 _pthread_start + 125
        28  libsystem_pthread.dylib             0x00007ff8156afc7b thread_start + 15
)
libc++abi: terminating with uncaught exception of type NSException
[1]    56724 abort      totem --configuration lib_2024
```

## Next Steps

Audit where the runtime updates window titles and constrain those calls to the main thread or replace them with SDL-safe messaging.
