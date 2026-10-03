# AI Agent 上輪問題修正回歸測試報告

測試時間：2026-08-15

## 修正結果摘要

已改善上輪列出的問題：

1. English WiFi password now uses the fixed WiFi credential answer and only references wireless pages.
2. English TANetRoaming now uses a focused fixed answer.
3. English eduroam roaming username now uses `sStudentID@wlan.nthu.edu.tw` and no Chinese text.
4. English general campus building WiFi questions now answer instead of rejecting.
5. English dorm network IP settings now use a fixed answer.
6. Question-language detection now lets Chinese questions return Chinese even when `language=en`, and English questions return English even when `language=zh-Hant`.

## Final General Building Retest

**Q：Does TSMC building have WiFi?**

TSMC building is treated as an NTHU campus building in this question. You can first try using NTHU campus Wi-Fi there.

If you can see `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam` on site, connect using the normal campus Wi-Fi method. If the signal is weak, the SSID does not appear, or the connection fails, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy

---

## 完整問答

### FIX01 EN WiFi password [en]

**Q：Is my NTHU WiFi password the same as AIS password?**

No. Your NTHU WiFi password is not the same as your Academic Information System password.

The WiFi account and password belong to the campus wireless LAN account, which must be applied for separately.

**Where it comes from**
1. Log in to the Academic Information System.
2. Enter the Network Systems Division online service from the Computer and Communication Center related services menu.
3. Select “Wireless LAN Account” and set your wireless LAN password.

For `nthupeap` or `eduroam` on campus, the account format is usually `sStudentID`. For `eduroam` roaming at another university, use `sStudentID@wlan.nthu.edu.tw`.

For details:
https://net.nthu.edu.tw/netsys/en:wireless:application
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth

### FIX02 EN TANetRoaming [en]

**Q：How do I use TANetRoaming?**

`TANetRoaming` uses browser login.

**How to use it**
1. Select `TANetRoaming` from the Wi-Fi list.
2. Open a browser after connecting. The login page should appear.
3. Enter your campus wireless LAN account and password to use the network.

**When using it at another university**
If the other university provides `TANetRoaming`, use your NTHU roaming account format: `sStudentID@wlan.nthu.edu.tw`.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth

### FIX03 EN eduroam account elsewhere [en]

**Q：What username should I use for eduroam at another university?**

For `eduroam` at another university, use your NTHU campus wireless LAN account in this format:

`sStudentID@wlan.nthu.edu.tw`

Use the password you set for your NTHU campus wireless LAN account. This password is not necessarily the same as your Academic Information System password.

After you select `eduroam` in the Wi-Fi list, enter the full account format above and save the setting.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_roaming
https://net.nthu.edu.tw/netsys/en:faq:wlan_auth

### FIX04 EN general building [en]

**Q：Does TSMC building have WiFi?**

Does TSMC building is treated as an NTHU campus building in this question. You can first try using NTHU campus Wi-Fi there.

If you can see `nthu-cc`, `TANetRoaming`, `nthupeap`, or `eduroam` on site, connect using the normal campus Wi-Fi method. If the signal is weak, the SSID does not appear, or the connection fails, contact wlan@cc.nthu.edu.tw with the exact location, floor, SSID, device OS, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:wlan_range
https://net.nthu.edu.tw/netsys/en:wireless:easy

### FIX05 EN Dorm IP [en]

**Q：Where should I enter the dorm network IP settings?**

After your dormitory network application is complete and processed at 10:00 or 16:00, enter the assigned TCP/IP settings in your device’s Ethernet network settings.

If you are using a router, ask “How do I connect a router to the dorm network?” For a computer directly connected by network cable, follow these steps:

1. Make sure the device is connected to the dormitory network wall port by network cable.
2. Open the device’s network settings and select Ethernet.
3. Edit the IP assignment setting.
4. Change automatic DHCP to manual or static IPv4.
5. Enter the assigned IP address, subnet mask, gateway, and DNS shown after your DormNet application, then save.
6. Test whether the device can access the Internet.

For help, contact dorms@cc.nthu.edu.tw with your dormitory room number, device OS, IP settings, error message, and screenshots.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config

### FIX06 Chinese question with English language [en]

**Q：宿網要怎麼申請？**

宿網申請共分成下面兩大步：

**申請宿舍網路帳號**

1. 先登入「校務資訊系統」。
2. 進入系統後，於左方選單點選「計通中心相關服務」裡的「網路系統組線上服務」。
3. 接著在右方點選「登入網路系統組線上服務」。
4. 在畫面下方點選「學生宿舍網路帳號」並確認目前申請裝置有連上學校網路，需在學校網域內申請。
5. 進入申請頁面後，請先閱讀「校園網路使用規範」與「學生宿舍網路使用規範」等規範。
6. 在畫面中間設定您的宿網密碼，並點選底部的「同意」按鈕。
7. 宿網帳號密碼設定完成後，目前僅完成帳號申請，請接續[申請宿舍網路](https://dormnet.nthu.edu.tw/~dormnet/cgi-bin/AP/A1.pl)。

**申請宿舍網路**

8. 進入宿舍網路申請頁面後，輸入剛剛在校務資訊系統設定的帳號密碼，電子郵件選取宿網帳號（DormNet Account）。
9. 接下來請填寫宿舍的相關資訊，申請型態選擇「登錄」。
10. 提出申請後會出現您申請到的宿網 IP 設定資訊，此資料會寄到您上一步填寫的 Email，請記得該 IP 的設定資訊，之後連接宿網會需要用到。
11. 您已完成宿網申請，提出申請後，每日 10 時與 16 時進行系統處理完畢後即可使用。

若對如何設定宿網 IP 有疑問的話，可繼續詢問「要怎麼設定宿舍網路」。

**尋求幫助**
若申請過程中遇到問題，或已申請後仍無法連線，請向宿網信箱 dorms@cc.nthu.edu.tw 提供宿舍房號、裝置系統、是否有設定 IP、錯誤訊息，並附上相關 IP 設定及網路狀況等截圖，以便技術人員協助。

詳細可參考：
https://net.nthu.edu.tw/netsys/faq:domitory_net_ua_apply

### FIX07 English question with Chinese language [zh-Hant]

**Q：How do I connect a router to dormnet?**

To connect a router to the dormitory network, connect the router WAN port to the dormitory network wall port and set the WAN connection type to static IP.

1. Connect the router WAN port to the dormitory network wall port.
2. Connect your computer or phone to the router. It may show no Internet connection before the WAN settings are complete.
3. Open the router management page. Common addresses include `192.168.1.1` or `192.168.0.1`, but use the address shown in your router manual.
4. In WAN, Internet, or external network settings, choose static IP.
5. Enter the IP address, subnet mask, gateway, and DNS settings assigned after your dormitory network application.
6. Save the settings and test whether your devices can access the Internet through the router.

For help, contact dorms@cc.nthu.edu.tw with your dormitory room number, router model, WAN settings screenshot, assigned IP settings, and error screenshot.

For details:
https://net.nthu.edu.tw/netsys/en:faq:domitory_network_config2
