{{- define "remediai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "remediai.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "remediai.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
