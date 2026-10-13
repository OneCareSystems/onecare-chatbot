<#
 One-time provisioning of the chatbot database on the EXISTING MySQL 8 instance.
 Creates: database onecare_chatbot, user chatbot_app with privileges ONLY on onecare_chatbot.
 Creates NO tables (tables come from `python manage.py migrate`). Safe to run twice.

 $env:MYSQL_ADMIN_PASSWORD = "<admin pw>"
 $env:CHATBOT_DB_PASSWORD  = "<new chatbot_app pw>"     # no ' or \ characters
 .\db\create_chatbot_schema.ps1 -MysqlHost 127.0.0.1 -AdminUser root -WithTestDbGrant   # dev/CI only
#>
param(
  [string]$MysqlHost = "127.0.0.1",
  [int]$Port = 3306,
  [string]$AdminUser = "root",
  [string]$UserHost = "localhost",   # staging/prod: the app server's host or subnet, e.g. '10.0.%'
  [switch]$WithTestDbGrant           # dev/CI only: lets pytest create test_onecare_chatbot
)
$ErrorActionPreference = "Stop"
if (-not $env:MYSQL_ADMIN_PASSWORD) { throw "Set MYSQL_ADMIN_PASSWORD" }
if (-not $env:CHATBOT_DB_PASSWORD)  { throw "Set CHATBOT_DB_PASSWORD" }
if ($env:CHATBOT_DB_PASSWORD -match "['\\]") { throw "CHATBOT_DB_PASSWORD must not contain ' or \" }

# Single-quoted here-string: PowerShell does not touch the backticks or backslashes.
$sql = @'
CREATE DATABASE IF NOT EXISTS `onecare_chatbot` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'chatbot_app'@'__HOST__' IDENTIFIED BY '__PW__';
ALTER USER 'chatbot_app'@'__HOST__' IDENTIFIED BY '__PW__';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
  ON `onecare\_chatbot`.* TO 'chatbot_app'@'__HOST__';
'@
if ($WithTestDbGrant) {
  $sql += "`nGRANT ALL PRIVILEGES ON ``test\_onecare\_chatbot``.* TO 'chatbot_app'@'__HOST__';"
}
$sql += "`nFLUSH PRIVILEGES;"
$sql = $sql.Replace("__HOST__", $UserHost).Replace("__PW__", $env:CHATBOT_DB_PASSWORD)

$env:MYSQL_PWD = $env:MYSQL_ADMIN_PASSWORD
try {
  $sql | mysql --protocol=tcp -h $MysqlHost -P $Port -u $AdminUser
  if ($LASTEXITCODE -ne 0) { throw "mysql exited with code $LASTEXITCODE" }
  Write-Host "OK: onecare_chatbot and chatbot_app are ready"
} finally { Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue }