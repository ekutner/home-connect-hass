param (
    [Parameter(Mandatory, Position=0, HelpMessage="Path to gallery folder")]
    [string]
    $path,

    [Parameter(HelpMessage="Path to template file with _album_ placeholder")]
    [string]
    $templateFile="album_template.html"
)

$dirs = Get-ChildItem $path -Directory
$template = Get-Content -Path $templateFile
Write-Host $template

$weight = 0
foreach($dir in $dirs) {
    $weight += 10
    $album = Split-Path $dir -Leaf
    $albumFile = $template.Replace('_album_', $album).Replace('_weight_', $weight)
    #Write-Host $albumFile
    $albumFile | Out-File -FilePath "$($album.ToLower()).md" -NoClobber
}

return

Function Get-FileMetaData
{

    Param([string[]]$folder)
    foreach($sFolder in $folder)
    {
        $a = 0
        $objShell = New-Object -ComObject Shell.Application
        $objFolder = $objShell.namespace($sFolder)

        foreach ($File in $objFolder.items())
        {
            $FileMetaData = New-Object PSOBJECT
            for ($a ; $a -le 266; $a++)
            {
                if($objFolder.getDetailsOf($File, $a))
                {
                    $hash += @{$($objFolder.getDetailsOf($objFolder.items, $a)) = $($objFolder.getDetailsOf($File, $a)) }
                    $FileMetaData | Add-Member $hash
                    $hash.clear()
                } #end if
            } #end for
            $a=0
            $FileMetaData
        } #end foreach $file
    } #end foreach $sfolder
} #end Get-FileMetaData


Get-FileMetaData -Folder $path