# Source Profile

Generated at: `2026-10-09T09:28:27.797498+00:00`

## Identity
- Source file: `drebin_dataset.csv`
- Relative path: `data/source/drebin_dataset.csv`
- SHA-256: `710f2c11b0cad04c36f56dd16398127feb697fd99e8efa7f75890b792fba3ad5`
- Size (bytes): 6514978
- Rows: 15036
- Columns: 216

## Target
- Target column: `class`
- Value counts:
  - `B`: 9476 (0.630221)
  - `S`: 5560 (0.369779)

## Duplicate audit

**Interpretation.** One source row is treated as one app observation. Two apps can legitimately share the same 215 binary flags, so identical feature vectors are not automatically duplicates. The default policy is to KEEP all rows to preserve the baseline population. Nothing is dropped at profile time.

### Exact duplicates (all columns, including target)
- Rows that are members of any exact-duplicate group: `10047`
- Rows beyond the first in each group (i.e. would be dropped by `drop_duplicates()`): `7775`
- Group-size distribution: `{1: 4989, 2: 1135, 3: 491, 4: 251, 5: 130, 6: 70, 7: 30, 8: 28, 9: 14, 10: 15, 11: 13, 12: 11, 13: 6, 14: 8, 15: 4, 16: 5, 17: 6, 18: 4, 19: 4, 20: 4, 21: 5, 22: 3, 23: 2, 24: 1, 25: 4, 26: 1, 27: 1, 29: 1, 31: 1, 34: 2, 37: 1, 40: 1, 41: 3, 42: 2, 48: 1, 56: 2, 59: 1, 60: 2, 65: 1, 97: 1, 98: 1, 120: 1, 134: 1, 136: 1, 145: 1, 268: 1, 377: 1}`

### Duplicate feature vectors (target ignored)
- Rows that are members of any duplicate-feature-vector group: `10049`
- Rows beyond the first in each group: `7778`
- Group-size distribution: `{1: 4987, 2: 1135, 3: 491, 4: 251, 5: 130, 6: 70, 7: 30, 8: 27, 9: 13, 10: 15, 11: 14, 12: 11, 13: 6, 14: 8, 15: 4, 16: 5, 17: 6, 18: 4, 19: 4, 20: 4, 21: 5, 22: 3, 23: 2, 24: 1, 25: 4, 26: 1, 27: 1, 29: 1, 31: 1, 34: 2, 37: 1, 40: 1, 41: 3, 42: 2, 48: 1, 56: 2, 59: 1, 60: 2, 65: 1, 97: 1, 98: 1, 120: 1, 134: 1, 136: 1, 145: 1, 268: 1, 385: 1}`

### Conflicting labels for identical feature vectors
- Groups with disagreeing labels: `3`
- Rows involved in those groups: `398`

Sample conflicting groups (first up to 10):

| group_size | label_counts |
|---:|---|
| 385 | {'B': 377, 'S': 8} |
| 11 | {'B': 9, 'S': 2} |
| 2 | {'S': 1, 'B': 1} |

**Policy.** These rows are **not** dropped or reassigned at profile time. The data contract declares how the pipeline behaves: keep, drop, or quarantine. Default is `keep` to preserve baseline reproduction. Any deviation must be declared in `metadata/data_contract.yml` and reflected in the reproducibility report.

## Column summary
| column | dtype | null_count | null_rate | unique_count | min | max | example_values |
|---|---:|---:|---:|---:|---:|---:|---|
| `transact` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `onServiceConnected` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `bindService` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `attachInterface` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ServiceConnection` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.os.Binder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SEND_SMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `Ljava.lang.Class.getCanonicalName` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getMethods` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.cast` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.net.URLDecoder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.content.pm.Signature` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.telephony.SmsManager` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `READ_PHONE_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `getBinder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ClassLoader` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Landroid.content.Context.registerReceiver` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `Ljava.lang.Class.getField` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Landroid.content.Context.unregisterReceiver` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `GET_ACCOUNTS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `RECEIVE_SMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getDeclaredField` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_SMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `getCallingUid` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljavax.crypto.spec.SecretKeySpec` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.BOOT_COMPLETED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `USE_CREDENTIALS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MANAGE_ACCOUNTS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.content.pm.PackageInfo` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `KeySpec` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getLine1Number` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `DexClassLoader` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `HttpGet.init` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SecretKey` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getMethod` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `System.loadLibrary` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.SEND` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljavax.crypto.Cipher` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_SMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_SYNC_SETTINGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `AUTHENTICATE_ACCOUNTS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.telephony.gsm.SmsManager` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_HISTORY_BOOKMARKS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getSubscriberId` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `mount` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `INSTALL_PACKAGES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Runtime.getRuntime` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CAMERA` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Object.getClass` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_SYNC_SETTINGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_HISTORY_BOOKMARKS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.forName` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `INTERNET` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `android.intent.action.PACKAGE_REPLACED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Binder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.SEND_MULTIPLE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `RECORD_AUDIO` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `IBinder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.os.IBinder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `createSubprocess` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `NFC` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCESS_LOCATION_EXTRA_COMMANDS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `URLClassLoader` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_APN_SETTINGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `abortBroadcast` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_REMOTEVIEWS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.TIME_SET` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_PROFILE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getDeviceId` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MODIFY_AUDIO_SETTINGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `getCallingPid` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_SYNC_STATS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BROADCAST_STICKY` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.PACKAGE_REMOVED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.TIMEZONE_CHANGED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WAKE_LOCK` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `RECEIVE_BOOT_COMPLETED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `RESTART_PACKAGES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getPackage` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `chmod` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getDeclaredClasses` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.ACTION_POWER_DISCONNECTED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.PACKAGE_ADDED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `PathClassLoader` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getSimSerialNumber` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Runtime.load` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getCallState` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BLUETOOTH` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_CALENDAR` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_CALL_LOG` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SUBSCRIBED_FEEDS_WRITE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_EXTERNAL_STORAGE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getSimCountryIso` | string | 0 | 0.0000 | 3 | None | None | 0, 1, ? |
| `sendMultipartTextMessage` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `PackageInstaller` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `VIBRATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `remount` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.ACTION_SHUTDOWN` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `sendDataMessage` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCESS_NETWORK_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `chown` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `HttpPost.init` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getClasses` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SUBSCRIBED_FEEDS_READ` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.isNetworkRoaming` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CHANGE_WIFI_MULTICAST_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_CALENDAR` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.PACKAGE_DATA_CLEARED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MASTER_CLEAR` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `HttpUriRequest` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `UPDATE_DEVICE_STATS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_CALL_LOG` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `DELETE_PACKAGES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `GET_TASKS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `GLOBAL_SEARCH` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `DELETE_CACHE_FILES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_USER_DICTIONARY` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.PACKAGE_CHANGED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.NEW_OUTGOING_CALL` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `REORDER_TASKS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_PROFILE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_WALLPAPER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_INPUT_METHOD` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `divideMessage` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_SOCIAL_STREAM` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_USER_DICTIONARY` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `PROCESS_OUTGOING_CALLS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CALL_PRIVILEGED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Runtime.exec` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_WALLPAPER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `RECEIVE_WAP_PUSH` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `DUMP` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BATTERY_STATS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCESS_COARSE_LOCATION` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_TIME` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.SENDTO` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_SOCIAL_STREAM` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_SETTINGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `REBOOT` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BLUETOOTH_ADMIN` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getNetworkOperator` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `/system/bin` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MessengerService` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_DEVICE_ADMIN` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_GSERVICES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `IRemoteService` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `KILL_BACKGROUND_PROCESSES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_ALARM` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCOUNT_MANAGER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `/system/app` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.CALL` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `STATUS_BAR` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `TelephonyManager.getSimOperator` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `PERSISTENT_ACTIVITY` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CHANGE_NETWORK_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `onBind` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Process.start` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.SCREEN_ON` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Context.bindService` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `RECEIVE_MMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_TIME_ZONE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.BATTERY_OKAY` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CONTROL_LOCATION_UPDATES` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BROADCAST_WAP_PUSH` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_ACCESSIBILITY_SERVICE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ADD_VOICEMAIL` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CALL_PHONE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ProcessBuilder` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_APPWIDGET` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `FLASHLIGHT` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_LOGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Ljava.lang.Class.getResource` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `defineClass` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_PROCESS_LIMIT` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.PACKAGE_RESTARTED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MOUNT_UNMOUNT_FILESYSTEMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_TEXT_SERVICE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `INSTALL_LOCATION_PROVIDER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.CALL_BUTTON` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.SCREEN_OFF` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `findClass` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SYSTEM_ALERT_WINDOW` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MOUNT_FORMAT_FILESYSTEMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CHANGE_CONFIGURATION` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CLEAR_APP_USER_DATA` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `intent.action.RUN` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.SET_WALLPAPER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CHANGE_WIFI_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_FRAME_BUFFER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCESS_SURFACE_FLINGER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `Runtime.loadLibrary` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BROADCAST_SMS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `EXPAND_STATUS_BAR` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `INTERNAL_SYSTEM_WINDOW` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.BATTERY_LOW` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_ACTIVITY_WATCHER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_CONTACTS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `android.intent.action.ACTION_POWER_CONNECTED` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `BIND_VPN_SERVICE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `DISABLE_KEYGUARD` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCESS_MOCK_LOCATION` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `GET_PACKAGE_SIZE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `MODIFY_PHONE_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CHANGE_COMPONENT_ENABLED_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `CLEAR_APP_CACHE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_ORIENTATION` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `READ_CONTACTS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `DEVICE_POWER` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `HARDWARE_TEST` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `ACCESS_WIFI_STATE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_EXTERNAL_STORAGE` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 1, 0 |
| `ACCESS_FINE_LOCATION` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_WALLPAPER_HINTS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `SET_PREFERRED_APPLICATIONS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `WRITE_SECURE_SETTINGS` | int64 | 0 | 0.0000 | 2 | 0.0 | 1.0 | 0, 1 |
| `class` | str | 0 | 0.0000 | 2 | None | None | S, B |