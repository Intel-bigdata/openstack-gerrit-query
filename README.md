# openstack-gerrit-query
 Gerrit query Python wrapper

This tool always needs two dates where the former is smaller than the latter.
```
tsocks python gerrit-query.py 2014-12-01 2015-01-01
```

If your server username is different with gerrit username,
```
tsocks python gerrit-query.py 2014-12-01 2015-01-01 -lzyluo
```

If you want to list the details of each change,
```
tsocks python gerrit-query.py 2014-12-01 2015-01-01 -lzyluo -v
```

If you want to view a specific project,
```
tsocks python gerrit-query.py 2014-12-01 2015-01-01 -lzyluo -pironic -v
```

If you want to view specifify multiple projects,
```
tsocks python gerrit-query.py 2014-12-01 2015-01-01 -lzyluo -pironic -psahara -v
```
