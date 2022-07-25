param (
    [Parameter(Mandatory, Position=0, HelpMessage="Path to project root")]
    [string]
    $project
)

$mypath = Split-Path -path $MyInvocation.MyCommand.Path


#& "$mypath\hugo.exe" -v --templateMetrics --templateMetricsHints --cleanDestinationDir
& "$mypath\hugo.exe" -v --templateMetrics --templateMetricsHints --minify
& "$mypath\hugo.exe" deploy -v --maxDeletes -1
#aws s3 sync public/ "s3://photos.kutner.org" --delete
