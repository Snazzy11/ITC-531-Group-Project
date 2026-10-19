## 3b
Traffic and errors are both tracked with a query against our counter. 

A bad value for traffic could be 0 or an unexpectedly large number. A value of zero indicates no traffic, not necessarily a problem but if traffic abruptly dropped that low or has remained at zero for an extended period of time it could indicate an issue with the service. An unexpectedly high value for traffic on the other hand might indicate malicious activity, such as bots. In either case, an examination of the service and its health is the right course of action.

A bad value for the error rate could technically be anything over 0, however errors are bound to happen and as such an error rate of 0 is unrealistic and should not be expected. Setting an error threshold at which errors MUST be investigated promptly would be a better approach. So if the error rate were to exceed 1-5% (as an example), prompt investigation is needed.

A counter must be wrapped in rate to mean anything because rate is the function that calculates the per-second average rate of incerease over a given time window, without it the counter only provides an arbitrary number of requests that have happened; however with it the counter and rate together actually describe how the application is responding at a given moment.

## 3c

See screenshots/dashboard.png for the screenshot of the dashboard.

### Error Rate query
100 *
sum(rate(seekr_requests_total{status=~"[45].."}[5m]))
/
sum(rate(seekr_requests_total[5m]))

### Request Rate query
sum(rate(seekr_requests_total[5m]))

## 3d
The labels attached are method, route, and status.

Method - GET, PUT, POST, DELETE, PATCH
Route - The route of each request in our application. /users, /items/{item_id}, etc.
Status - The HTTP status code of the request. 200s, 300s, 400s, 500s

All three values are bounded, there exist a limited set of HTTP methods and statuses. The route label is the matched route template, read after a route has run, so it is bounded as well. 