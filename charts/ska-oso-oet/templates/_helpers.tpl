{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "ska-oso-oet.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ska-oso-oet.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "ska-oso-oet.labels" }}
app: {{ template "ska-oso-oet.name" . }}
chart: {{ template "ska-oso-oet.chart" . }}
release: {{ .Release.Name }}
heritage: {{ .Release.Service }}
system: {{ .Values.system }}
subsystem: {{ .Values.subsystem }}
telescope: {{ .Values.telescope }}
telescope: {{ .Values.semantic_validation }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ska-oso-oet.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Get the major version of the release
*/}}
{{- define "ska-oso-oet.major-version" }}
{{- with $x := printf "%s" .Chart.Version | split "."}}{{index $x "_0"}}{{end}}
{{- end -}}
