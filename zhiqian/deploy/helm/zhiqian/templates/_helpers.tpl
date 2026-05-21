/*
v2-step-18: Helm helpers
*/

- define "zhiqian.name" -
- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -
- end -

- define "zhiqian.fullname" -
- if .Values.fullnameOverride -
- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -
- else -
- $name := default .Chart.Name .Values.nameOverride -
- if contains $name .Release.Name -
- .Release.Name | trunc 63 | trimSuffix "-" -
- else -
- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -
- end -
- end -
- end -

- define "zhiqian.chart" -
- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -
- end -

- define "zhiqian.labels" -
helm.sh/chart:  include "zhiqian.chart" . 
app.kubernetes.io/name:  include "zhiqian.name" . 
app.kubernetes.io/instance:  .Release.Name 
app.kubernetes.io/managed-by:  .Release.Service 
app.kubernetes.io/version:  .Chart.AppVersion | quote 
app.kubernetes.io/part-of: zhiqian
- end -

/* component-specific selector labels */
- define "zhiqian.selectorLabels" -
app.kubernetes.io/name:  include "zhiqian.name" . 
app.kubernetes.io/instance:  .Release.Name 
app.kubernetes.io/component:  .component 
- end -

- define "zhiqian.image" -
- $registry := .global.imageRegistry -
- $repo := .image.repository -
- $tag := .image.tag | default .appVersion -
- if $registry -
- printf "%s/%s:%s" $registry $repo $tag -
- else -
- printf "%s:%s" $repo $tag -
- end -
- end -

- define "zhiqian.serviceAccountName" -
- if .Values.serviceAccount.create -
- default (include "zhiqian.fullname" .) .Values.serviceAccount.name -
- else -
- default "default" .Values.serviceAccount.name -
- end -
- end -
