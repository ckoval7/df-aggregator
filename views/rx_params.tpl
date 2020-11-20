% for x in {{receivers}}:
<RECEIVER>
  <STATION_ID>{{x.station_id}}</STATION_ID>
  <URL>{{x.station_url}}</URL>
  <AUTO>{{x.isAuto}}</AUTO>
  <FREQUENCY>{{x.frequency}}</FREQUENCY>
  <LATITUDE>{{x.latitude}}</LATITUDE>
  <LONGITUDE>{{x.longitude}}</LONGITUDE>
  <HEADING>{{x.heading}}</HEADING>
  <MOBILE>{{x.isMobile}}</MOBILE>
</RECEIVER>
% end
