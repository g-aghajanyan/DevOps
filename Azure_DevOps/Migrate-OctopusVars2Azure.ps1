#Azure vars
$pipelineName = '_'
$projectaz = "_"

#Octo vars
$projectname = '_'
$projectvars = Get-OctopusVariableSet -ProjectName $projectname 
$envnames = @('CI','Test', 'UAT', 'DR', 'Production')

$toFile = 'Y' # N: Update Pipline Variabe, Y: Create yaml file for Non sensitive Vraiables
$variablesFilePath = "C:\Code\project_vars_"


foreach ($envname in $envnames) {
    $outfilename = $variablesFilePath+$envname+".yaml"
    foreach ($projectvar in $projectvars.Variables) {
        if ($projectvar.Scope.Environments -contains $envname) {
#            Rename Production to Prod
            # if ($envname -eq 'Production') { 
            #     $envnamerenamed = 'Prod'
            # } else {
            #     $envnamerenamed = $envname
            # }
            if ($projectvar.IsSensitive -ne 'False') {
                if ($toFile -eq 'N') {
                    az pipelines variable create --pipeline-name $pipelineName --name "$($projectvar.Name).$envnamerenamed" --value $projectvar.Value --output table --project $projectaz
                } elseif ($toFile -eq 'Y') {
                    Add-Content "$outfilename" "$($projectvar.Name): $($projectvar.Value)"

                    #echo "$envname - $($projectvar.Name): $($projectvar.Value)"
                }             
            } else {
                # az pipelines variable create --pipeline-name $pipelineName --name "$($projectvar.Name).$envname" --value "secret" --secret --output table --project $projectaz
                Add-Content "$outfilename" "$($projectvar.Name): `$($($projectvar.Name).`${{parameters.Enviroment}})"
            }
        }
    }
}


