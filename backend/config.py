import platform

IS_RASPBERRY_PI = platform.machine().startswith('arm') or platform.machine().startswith('aarch')

if IS_RASPBERRY_PI:
    CAMERA_INDEX = 0
    HOST = "0.0.0.0"
    PORT = 8000
    USE_THREADING = True
else:
    CAMERA_INDEX = 0
    HOST = "0.0.0.0"
    PORT = 8000
    USE_THREADING = True

VIDEO_WIDTH = 640
VIDEO_HEIGHT = 483
FPS = 30

GENFILES_PATH = "genfiles"
CPP_MODULE_PATH = "../cpp_modules/rgb_correction.dll"

BRIGHTNESS_MIN = 7
BRIGHTNESS_MAX = 60
BRIGHTNESS_DEFAULT = 40
