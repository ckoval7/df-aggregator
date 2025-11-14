## Recent Changes:
- Bug fixes (January 2025)
  - Fixed loading spinner staying visible when CZML data fails to load
  - Added error handler to loadTxCzml() to ensure spinner is always hidden
- Update to czml3 3.0.0 (January 2025)
  - **Breaking Change**: Replaced `Preamble` class with `Packet(id="document", name="...", version=CZML_VERSION)`
  - **Breaking Change**: `Document()` now requires keyword argument `packets=` instead of positional list
  - **Breaking Change**: `dumps()` method no longer accepts `separators` argument
  - **Breaking Change**: Property validation now strict with Pydantic
    - Removed invalid `zIndex` property from Point and Billboard (not supported)
    - Changed `heightReference` from string to dict: `{"heightReference": "CLAMP_TO_GROUND"}`
    - Changed Polyline `positions` from `Position` to `PositionList`
    - Kept `zIndex` in Ellipse properties (valid for Ellipse)
  - Fixed incorrect use of `Material` class for polyline materials
  - Changed to use `PolylineMaterial` for polyline-specific materials (polylineOutline, polylineDash)
  - Updated all Document() calls to use `Document(packets=[...])` syntax
  - Updated all dumps() calls to remove separators argument
  - Removed unused `Material` import and `Preamble` import
  - Now imports `CZML_VERSION` and `PositionList` from czml3
  - Updated requirements to czml3 >= 1.0.0 (now maintained by Stoops-ML)
  - Note: czml3 v2.0+ uses Pydantic for all classes with strict validation
- Update to CesiumJS 1.135 (November 2025)
  - Migrated from deprecated `imageryProvider` option to modern `baseLayer` API
  - Updated to use `ArcGisMapServerImageryProvider.fromUrl()` async pattern
  - Updated to use `ImageryLayer.fromProviderAsync()` for imagery layer initialization
  - Using official Cesium CDN for latest version (1.135)
- Update to CesiumJS 1.95
- Power and Confidence range sliders have been updated to reflect data output by the KrakenSDR software.

## Previous Changes
- Ellipse parameters are now automatically calculated. You can still adjust them
if you want, but the auto-calculation works exceptionally well.
- LOB Length is now determined by the distance to the furthest intersection from
the receiver.
- Fixed bug where map lags behind the receiver.
- Changed the way ellipse and clustering parameters are handled. This allows for
multi-user map interaction.
- Updated to Cesium 1.79
- The LOB for each receiver on the map changes color based on the power and
  confidence thresholds.
    - Green when both power and confidence are above their thresholds
    - Orange when just power is above it's threshold.
    - Red when power is below it's minimum threshold.
- Receivers on map update every 2.5 Seocnds.
    - To customize this change `refreshrate` at the top of `static/receiver_configurator.js`.
- Your old database files will not work directly with this latest commit. Several changes have been made
  to the database structure to accomodate new features.
- Now introducing Single Receiver Mode! This will give you functionality similar to, but better than
  the Kerberos SDR Android App. You can define multiple search areas, or even just define areas you
  know where the transmitter isn't located.
- The access token is now optional.
- Be on the lookout for documention and tutorials between Christmas and New Years.
- Behind the scenes, there have been several optimizations.
- Added option to invert (uninvert?) the DOA bearing. If you're using a KerberosSDR,
  keep this option checked.
- LOBs are drawn for each receiver. The orange lines extending from each receiver
  show the direction the signal is coming from. Currently the line is fixed to 40km
  draw distance.
- Receivers can be added from the WebUI
    - Click the + at the bottom of the receiver cards, enter the URL, click save.
    Click the refresh button to update the cards and map.
- A list of receiver URLs is now optional. Receivers are saved to the database.
    - Receivers are read from the database first. Duplicate receiver URLs are ignored.
- You can mark a receiver as mobile.
    - Click the edit icon for the applicable receiver, click the checkbox to mark
      it as mobile, then click save.
- You can now delete receivers from the list. This will remove it from the map
and database. No historical data is affected.
- You can now enable/disable LOB collection from individual receivers.
Click the power button to enable/disable.
    - Black is enabled, red is disabled.
- If you lose connectivity to a receiver, that particular receiver will be disabled.
  Click the power button to try to reconnect.
- ~~Map refreshes every 5 seconds. Change `refreshrate` at the top of `static/receiver_configurator.js` to change the refresh rate.~~
