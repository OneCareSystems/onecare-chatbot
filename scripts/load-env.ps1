param([string]$Path = ".env")
Get-Content $Path | ForEach-Object {
  $line = $_.Trim()
  if ($line -eq "" -or $line.StartsWith("#")) { return }
  $k, $v = $line -split "=", 2
  $v = ($v -split "\s+#")[0].Trim().Trim('"')     # drops trailing " # comment"
  [Environment]::SetEnvironmentVariable($k.Trim(), $v, "Process")
}