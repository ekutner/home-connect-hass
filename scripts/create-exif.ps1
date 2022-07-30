param (
    [Parameter( Position=0, HelpMessage="Path to gallery folder")]
    [string]
    $path="d:\pictures\_gallery\",

    [Parameter(HelpMessage="Recurse subdirectories")]
    [Switch]
    $recurse=$false
)

Function Get-FileMetaData {
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


$folders = @( $path )
if ($recurse) {
    $folders += Get-ChildItem -Path $path -Recurse -Directory -Exclude ".*"
}

#.\exiftool.exe -q -q -j -struct --History --XMP-crs:all --ICC_Profile:all --IFD1:all --Adobe:all -w %d/.meta/%F.json D:\Pictures\_Gallery\Portfolio\5D4_2217.jpg

foreach ($folder in $folders) {
    Write-Host "Processing $folder"
    $exifFolder = Join-Path $folder ".metadata"
    Remove-Item -Path $exifFolder -Force -Recurse -ErrorAction SilentlyContinue
    $metadata = Get-FileMetaData $folder | Where-Object {  @("Picture", "Video") -contains $_.Kind }
     if ($null -ne $metadata) {
        ## Write into a single file
        # $metadict = @{}
        # $metadata | %{$metadict.Add($_.Filename, $_)}
        # $metadict | ConvertTo-Json | Out-File -FilePath $exifFolder -Encoding utf8

        ## Write a file per image into a .metadata directory
        #New-Folder $exifFolder
        New-Item -Path $exifFolder -ItemType Directory -ErrorAction SilentlyContinue | Out-Null
        foreach ($meta in $metadata) {
            $fileName = Join-Path $exifFolder "$($meta.Filename).json"
            #$meta | ConvertTo-Json | write-host
            $meta | ConvertTo-Json | Out-File -FilePath $fileName
        }
     }
}

