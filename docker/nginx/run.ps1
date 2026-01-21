docker run -d `
  --name ometa-nginx `
  --network om-net `
  -v openmetadata_ingestion-volume-tmp:/usr/share/nginx/html/reports:ro `
  -v "D:\python_projects\om-testing\docker\nginx\nginx.conf:/etc/nginx/conf.d/default.conf:ro" `
  -p 81:80 `
  nginx:stable-trixie-perl