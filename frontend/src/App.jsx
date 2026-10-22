import { useEffect, useState } from "react";

import Sidebar from "./components/Sidebar";
import Login from "./pages/Login";

import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import NewProject from "./pages/NewProject";
import ProjectDetail from "./pages/ProjectDetail";
import Upload from "./pages/Upload";
import Processing from "./pages/Processing";
import DocumentRoutingReview from "./pages/DocumentRoutingReview";
import FoundationTableReview from "./pages/FoundationTableReview";
import FoundationGeometryReview from "./pages/FoundationGeometryReview";
import ContinuousFoundationReview from "./pages/ContinuousFoundationReview";
import IncidentReview from "./pages/IncidentReview";
import Results from "./pages/Results";
import ContinuousFoundationResults from "./pages/ContinuousFoundationResults";
import Analyses from "./pages/Analyses";
import PlaceholderView from "./components/PlaceholderView";
import Motor3D from "./pages/Motor3D";
import Exp02Annotator from "./pages/Exp02Annotator";

import {
  INITIAL_FILES,
  MAX_FILE_SIZE_BYTES,
  MAX_FILES_PER_ANALYSIS,
  MAX_TOTAL_SIZE_BYTES,
  isPdfFile,
} from "./config/upload";
import {
  assertCompatibleBackend,
  consultarEstado,
  iniciarAnalisis,
} from "./services/api";
import { loadWorkspace, saveWorkspace, downloadWorkspace, readSession, writeSession } from "./services/workspaceStorage";

const INITIAL_WORKSPACE = { projects: [], analyses: [] };

function App() {
  // =========================================================
  // AUTENTICACIÓN
  // =========================================================

  const [isAuthenticated, setIsAuthenticated] = useState(readSession);

  // =========================================================
  // NAVEGACIÓN
  // =========================================================

  const [activeView, setActiveView] = useState("dashboard");

  const [selectedProjectId, setSelectedProjectId] = useState(null);

  // =========================================================
  // PROYECTOS
  // =========================================================

  const [projects, setProjects] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  const [storageReady, setStorageReady] = useState(false);
  const [storageWritable, setStorageWritable] = useState(false);
  const [storageError, setStorageError] = useState("");
  const [saveAttempt, setSaveAttempt] = useState(0);
  const [backendStatus, setBackendStatus] = useState(null);
  const [backendError, setBackendError] = useState("");

  // =========================================================
  // UPLOAD / PROCESAMIENTO
  // =========================================================

  const [files, setFiles] = useState(INITIAL_FILES);

  const [screen, setScreen] = useState("idle");

  const [progress, setProgress] = useState(0);

  const [error, setError] = useState("");

  const [currentResults, setCurrentResults] = useState(null);
  const [currentResultsProjectId, setCurrentResultsProjectId] = useState(null);

  const [uploadingProjectId, setUploadingProjectId] =
    useState(null);

  const [routingReview, setRoutingReview] = useState(null);
  const [tableReview, setTableReview] = useState(null);
  const [geometryReview, setGeometryReview] = useState(null);
  const [incidentReview, setIncidentReview] = useState(null);

  const [pendingAnalysis, setPendingAnalysis] = useState(null);

  // =========================================================
  // NUEVO PROYECTO
  // =========================================================

  const [showNewProject, setShowNewProject] = useState(false);

  // =========================================================
  // PERSISTENCIA
  // =========================================================

  useEffect(() => {
    let active = true;
    loadWorkspace(INITIAL_WORKSPACE).then(({ data, error }) => {
      if (!active) return;
      setProjects(data.projects);
      setAnalyses(data.analyses);
      setStorageError(error ? error.message : "");
      setStorageWritable(!error);
      setStorageReady(true);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!storageReady || !storageWritable) return;
    let active = true;
    saveWorkspace({ projects, analyses }).then(() => {
      if (active) setStorageError("");
    }).catch((error) => {
      if (active) setStorageError(error.message || "No se pudo guardar el historial.");
    });
    return () => { active = false; };
  }, [projects, analyses, storageReady, storageWritable, saveAttempt]);

  useEffect(() => {
    let active = true;
    consultarEstado()
      .then(assertCompatibleBackend)
      .then((status) => {
        if (!active) return;
        setBackendStatus(status);
        setBackendError("");
      })
      .catch((statusError) => {
        if (!active) return;
        setBackendStatus(null);
        setBackendError(statusError.message || "No se pudo verificar la versión del backend.");
      });
    return () => { active = false; };
  }, []);

  // =========================================================
  // LOGIN
  // =========================================================

  function handleLogin() {
  writeSession(true);

  setIsAuthenticated(true);

  setActiveView("dashboard");
  setSelectedProjectId(null);
  setUploadingProjectId(null);
  setScreen("idle");
  setCurrentResults(null);
  setRoutingReview(null);
  setGeometryReview(null);
  setPendingAnalysis(null);
}

  // =========================================================
  // LOGOUT
  // =========================================================

  function handleLogout() {
    setIncidentReview(null);
    writeSession(false);

    setIsAuthenticated(false);

    setActiveView("dashboard");
    setSelectedProjectId(null);
    setUploadingProjectId(null);
    setScreen("idle");
    setFiles(INITIAL_FILES);
    setError("");
    setProgress(0);
    setCurrentResults(null);
    setRoutingReview(null);
    setGeometryReview(null);
    setPendingAnalysis(null);
  }

  // =========================================================
  // ANALISIS
  // =========================================================

  function openAnalysis(analysisId) {
    const analysis = analyses.find((item) => item.id === analysisId);
    if (!analysis?.resultado || analysis.projectId !== selectedProjectId) {
      setError("Este análisis anterior no contiene resultados guardados. Cargá los PDF en un análisis nuevo.");
      setActiveView("analysis");
      return;
    }
    setError("");
    setCurrentResults(analysis.resultado);
    setCurrentResultsProjectId(analysis.projectId);
    setScreen("results");
    setActiveView("results");
}

function backToAnalyses() {
  setCurrentResults(null);
  setScreen("idle");
  setActiveView("analysis");
}

  // =========================================================
  // ARCHIVOS
  // =========================================================

  function handleFilesSelected(selectedFiles) {
    setIncidentReview(null);
    const received = Array.from(selectedFiles || []);

    if (!received.length) {
      return;
    }

    const invalid = received.find((file) => !isPdfFile(file));
    if (invalid) {
      setError(`${invalid.name}: solo se aceptan archivos PDF.`);
      return;
    }

    const oversized = received.find(
      (file) => file.size > MAX_FILE_SIZE_BYTES
    );
    if (oversized) {
      setError(`${oversized.name}: supera el límite de 25 MB.`);
      return;
    }

    const existingKeys = new Set(
      files.map(
        (file) => `${file.name}:${file.size}:${file.lastModified}`
      )
    );
    const newFiles = received.filter(
      (file) =>
        !existingKeys.has(
          `${file.name}:${file.size}:${file.lastModified}`
        )
    );
    const combined = [...files, ...newFiles];

    if (combined.length > MAX_FILES_PER_ANALYSIS) {
      setError(
        `Se admiten hasta ${MAX_FILES_PER_ANALYSIS} archivos por análisis.`
      );
      return;
    }

    const totalBytes = combined.reduce(
      (total, file) => total + file.size,
      0
    );
    if (totalBytes > MAX_TOTAL_SIZE_BYTES) {
      setError("La carga completa supera el límite de 250 MB.");
      return;
    }

    setFiles(combined);
    setTableReview(null);
    setGeometryReview(null);
    setError("");
    setRoutingReview(null);
    setPendingAnalysis(null);
  }

  function clearFile(index) {
    setIncidentReview(null);
    setTableReview(null);
    setGeometryReview(null);
    setFiles((currentFiles) =>
      currentFiles.filter((_, currentIndex) => currentIndex !== index)
    );
    setRoutingReview(null);
    setPendingAnalysis(null);
    setError("");
  }

  // =========================================================
  // INICIAR ANÁLISIS
  // =========================================================

  function updateDocumentReview(projectId, review) {
    setProjects(items => items.map(item => item.id === projectId ? { ...item, clasificacionDocumental: review, updated: "Ahora" } : item));
    if (uploadingProjectId === projectId) setRoutingReview(review);
  }

  async function startAnalysis(assignments = null, tableDecision = null, executeCalculation = false, geometryDecision = null) {
    try {
      const status = assertCompatibleBackend(
        backendStatus || await consultarEstado()
      );
      setBackendStatus(status);
      setBackendError("");
    } catch (statusError) {
      const message = statusError instanceof Error
        ? statusError.message
        : "No se pudo verificar la versión del backend.";
      setBackendError(message);
      setError(message);
      return;
    }

    if (uploadingProjectId === null) {
      setError(
        "Primero seleccioná un proyecto antes de iniciar un análisis."
      );
      return;
    }

    if (!files.length) {
      setError("Cargá al menos un documento PDF.");
      return;
    }

    const project = projects.find(
      (item) => item.id === uploadingProjectId
    );

    if (!project) {
      setError("No se encontró el proyecto seleccionado.");
      return;
    }

    // Este sello se crea al enviar el formulario, nunca durante el render.
    // eslint-disable-next-line react-hooks/purity
    const now = Date.now();
    const draft =
      pendingAnalysis
        ? pendingAnalysis
        : {
            id: now,
            projectId: uploadingProjectId,
            number:
              analyses.filter(
                (analysis) => analysis.projectId === uploadingProjectId
              ).length + 1,
            date: new Date().toISOString(),
            documents: files.length,
            documentsData: files.map((file, index) => ({
              id: `${now}-doc-${index + 1}`,
              slotId: `doc-${String(index + 1).padStart(3, "0")}`,
              type: "Plano estructural",
              name: file.name,
              size: file.size,
              uploadedAt: new Date().toISOString(),
            })),
          };

    setPendingAnalysis(draft);
    if (tableDecision) setTableReview((current) => ({ ...current, decision: tableDecision }));
    setProjects((currentProjects) =>
      currentProjects.map((item) =>
        item.id === uploadingProjectId
          ? { ...item, status: "En análisis", updated: "Ahora" }
          : item
      )
    );

    setError("");
    setCurrentResults(null);
    setRoutingReview(null);
    setProgress(8);
    setScreen("processing");
    setActiveView("analysis");

    const progressInterval = window.setInterval(() => {
      setProgress((currentProgress) =>
        Math.min(currentProgress + 6, 92)
      );
    }, 250);

    try {
      const response = await iniciarAnalisis(files, assignments, tableDecision, uploadingProjectId, executeCalculation, null, null, geometryDecision);

      window.clearInterval(progressInterval);

      if (response.estado === "requiere_revision") {
        setIncidentReview(response);
        setProgress(0);
        setProjects((items) => items.map((item) => item.id === uploadingProjectId ? { ...item, status: "Revisión requerida", updated: "Ahora" } : item));
        setScreen("incident-review");
        setActiveView("documentation");
        return;
      }
      setIncidentReview(null);

      if (response.estado === "requiere_revision_geometria") {
        setProgress(0);
        setGeometryReview(response.revision_geometria);
        setRoutingReview(response.enrutamiento);
        setProjects((items) => items.map((item) => item.id === uploadingProjectId ? { ...item, status: "Revisión geométrica requerida", updated: "Ahora" } : item));
        setScreen("geometry-review");
        setActiveView("documentation");
        return;
      }

      if (response.estado === "requiere_revision_cuadro") {
        setProgress(0);
        setTableReview({ ...response.revision_cuadro, asignaciones: response.enrutamiento.asignaciones });
        setProjects((items) => items.map((item) => item.id === uploadingProjectId ? { ...item, status: "Revisión requerida", updated: "Ahora" } : item));
        setScreen("table-review");
        setActiveView("documentation");
        return;
      }

      if (["clasificacion_documental", "requiere_revision_documental"].includes(response.estado)) {
        setTableReview(null);
        setGeometryReview(null);
        setProgress(0);
        setRoutingReview(response.enrutamiento);
        setProjects((currentProjects) =>
          currentProjects.map((item) =>
            item.id === uploadingProjectId
              ? { ...item, status: "Documentación clasificada", clasificacionDocumental: response.enrutamiento, updated: "Ahora" }
              : item
          )
        );
        setScreen("routing-review");
        setActiveView("documentation");
        return;
      }

      const results = response.resultado;
      const computedVolume =
        results.volumen_cimientos_corridos_m3 ??
        results.volumen_hormigon_m3 ??
        0;
      const concreteVolume = Number(results.volumen_hormigon_m3 || 0);
      setTableReview(null);
      setGeometryReview(null);
      setProgress(100);
      setCurrentResults(results);
      setCurrentResultsProjectId(uploadingProjectId);

      const completedAnalysis = {
            ...draft,
            backendId: response.analisis_id,
            status: "Completado",
            confidence: results.confianza_lectura_porcentaje,
            volume: concreteVolume,
            geometricVolume: computedVolume,
            references: results.cantidad_fundaciones,
            foundationTypes: results.cantidad_tipos,
            resultado: results,
      };

      setAnalyses((currentAnalyses) => [
        ...currentAnalyses.filter((analysis) => analysis.id !== draft.id),
        completedAnalysis,
      ]);

      const existingDocuments = project.documentsData || [];
      setProjects((currentProjects) =>
        currentProjects.map((item) => {
          if (item.id !== uploadingProjectId) return item;
          return {
            ...item,
            documents: existingDocuments.length + draft.documentsData.length,
            documentsData: [...existingDocuments, ...draft.documentsData],
            analyses: (item.analyses || 0) + 1,
            status: "Completado",
            volume: `${concreteVolume.toFixed(3)} m³`,
            volumeValue: concreteVolume,
            updated: "Ahora",
          };
        })
      );

      setRoutingReview(null);
      setPendingAnalysis(null);

      window.setTimeout(() => {
        setScreen("results");
        setActiveView("results");
      }, 350);
    } catch (analysisError) {
      window.clearInterval(progressInterval);
      setProgress(0);
      setError(
        analysisError instanceof Error
          ? analysisError.message
          : "No se pudo completar el análisis."
      );
      setProjects((currentProjects) =>
        currentProjects.map((item) =>
          item.id === uploadingProjectId
            ? { ...item, status: tableReview || geometryReview || routingReview ? "Revisión requerida" : "Error", updated: "Ahora" }
            : item
        )
      );
      setRoutingReview(routingReview);
      setScreen(incidentReview ? "incident-review" : tableReview ? "table-review" : geometryReview ? "geometry-review" : routingReview ? "routing-review" : "upload");
      setActiveView("documentation");
    }
  }

  function backToUploadedFiles() {
    setTableReview(null);
    setIncidentReview(null);
    setGeometryReview(null);
    setRoutingReview(null);
    setPendingAnalysis(null);
    setError("");
    setProgress(0);
    setScreen("upload");
    setActiveView("documentation");
  }

  // =========================================================
  // NAVEGACIÓN GENERAL / PROYECTO
  // =========================================================

  function navigate(view) {
    setShowNewProject(false);
    if (uploadingProjectId === selectedProjectId && (view === "documentation" || view === "results")) {
      if (screen === "processing") return;
      if (incidentReview || tableReview || geometryReview || routingReview) {
        setScreen(incidentReview ? "incident-review" : tableReview ? "table-review" : geometryReview ? "geometry-review" : "routing-review");
        setActiveView("documentation");
        return;
      }
      if (error && files.length) {
        setScreen("upload");
        setActiveView("documentation");
        return;
      }
    }

    // Dashboard general
    if (view === "dashboard") {
      setSelectedProjectId(null);
      setUploadingProjectId(null);
      setScreen("idle");
      setActiveView("dashboard");
      return;
    }

    // Lista de proyectos
    if (view === "projects") {
      setSelectedProjectId(null);
      setUploadingProjectId(null);
      setScreen("idle");
      setActiveView("projects");
      return;
    }

    // Documentación dentro del proyecto
    if (view === "documentation") {
      if (selectedProjectId === null) {
        setActiveView("documentation");
        setScreen("idle");
        return;
      }

      setUploadingProjectId(selectedProjectId);
      setFiles(INITIAL_FILES);
      setError("");
      setProgress(0);
      setRoutingReview(null);
      setGeometryReview(null);
      setPendingAnalysis(null);
      setScreen("upload");
      setActiveView("documentation");
      return;
    }

    // Análisis dentro del proyecto
    if (view === "analysis") {
      setScreen("idle");
      setActiveView("analysis");
      return;
    }

    // Resultados dentro del proyecto
    if (view === "results") {
      setScreen("idle");
      setActiveView("results");
      return;
    }

    if (view === "model-3d") {
  setScreen("idle");
  setActiveView("model-3d");
  return;
}

    // Reportes dentro del proyecto
    if (view === "reports") {
      setScreen("idle");
      setActiveView("reports");
      return;
    }

    // Resumen del proyecto
    if (view === "project-overview") {
      setScreen("idle");
      setActiveView("project-overview");
      return;
    }

    setActiveView(view);
  }

  // =========================================================
  // CREAR PROYECTO
  // =========================================================

  function handleCreateProject(project) {
    const newProject = {
      // Solo se ejecuta al confirmar el formulario, no durante el render.
      // eslint-disable-next-line react-hooks/purity
      id: Date.now(),
      name: project.name,
      client: project.client,
      location: project.location,
      type: project.type,
      description: project.description,

      status: "Pendiente",

      documents: 0,
      analyses: 0,

      volume: "—",
      volumeValue: 0,

      updated: "Ahora",

      documentsData: [],
    };

    setProjects((currentProjects) => [
      newProject,
      ...currentProjects,
    ]);

    setShowNewProject(false);
    handleUploadForProject(newProject.id);
  }

  // =========================================================
  // ABRIR PROYECTO
  // =========================================================

function openProject(projectId) {
    setIncidentReview(null);
  setTableReview(null);
  setGeometryReview(null);
  setError("");
  setSelectedProjectId(projectId);
  const hasAnalyses = analyses.some((analysis) => analysis.projectId === projectId);
  setUploadingProjectId(hasAnalyses ? null : projectId);
  setFiles(INITIAL_FILES);
  setScreen(hasAnalyses ? "idle" : "upload");
  setCurrentResults(null);
  setRoutingReview(null);
  setPendingAnalysis(null);
  setActiveView(hasAnalyses ? "analysis" : "documentation");
}

  // =========================================================
  // CARGAR DOCUMENTACIÓN DEL PROYECTO
  // =========================================================

  function handleUploadForProject(projectId) {
    setIncidentReview(null);
    setTableReview(null);
    setGeometryReview(null);
    setSelectedProjectId(projectId);
    setUploadingProjectId(projectId);

    setFiles(INITIAL_FILES);
    setError("");
    setProgress(0);
    setCurrentResults(null);
    setRoutingReview(null);
    setPendingAnalysis(null);

    setScreen("upload");
    setActiveView("documentation");
  }

  // =========================================================
  // VOLVER A PROYECTOS
  // =========================================================

  function backToProjects() {
  setSelectedProjectId(null);
  setUploadingProjectId(null);

  setScreen("idle");
  setActiveView("projects");
}

  function downloadResults(results) {
    if (!results) {
      return;
    }

    const blob = new Blob(
      [JSON.stringify(results, null, 2)],
      { type: "application/json;charset=utf-8" }
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "resumen_computoestia.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  // =========================================================
  // SIDEBAR
  // =========================================================

  const selectedProject =
    selectedProjectId !== null
      ? projects.find(
          (project) =>
            project.id === selectedProjectId
        )
      : null;

  // =========================================================
  // LOGIN
  // =========================================================

  if (!storageReady) return <main className="p-10" role="status">Recuperando proyectos y análisis…</main>;

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  // =========================================================
  // CONTENIDO
  // =========================================================

  function renderContent() {
    if (showNewProject) {
      return (
        <NewProject
          onCancel={() => setShowNewProject(false)}
          onCreate={handleCreateProject}
        />
      );
    }

    // EXP-02 Ground Truth
      if (activeView === "exp02") {
        return <Exp02Annotator dataset="exp02" />;
      }

    // EXP16 · Nuevos proyectos independientes
      if (activeView === "exp16") {
        return <Exp02Annotator dataset="exp16" />;
      }

    // -------------------------------------------------------
    // DENTRO DE UN PROYECTO
    // -------------------------------------------------------

    if (selectedProjectId !== null) {
      const project = projects.find(
        (item) => item.id === selectedProjectId
      );

      if (!project) {
        return (
          <PlaceholderView
            title="Proyecto no encontrado"
            description="El proyecto seleccionado ya no está disponible."
            icon="folder"
            action="Volver a proyectos"
            onAction={backToProjects}
          />
        );
      }

      const latestResult = [...analyses]
        .filter(
          (analysis) =>
            analysis.projectId === selectedProjectId &&
            analysis.status === "Completado" &&
            analysis.resultado
        )
        .sort(
          (first, second) =>
            new Date(second.date).getTime() -
            new Date(first.date).getTime()
        )[0]?.resultado;

      const visibleResults =
        (currentResultsProjectId === selectedProjectId ? currentResults : null) || latestResult;

      if (uploadingProjectId === selectedProjectId && screen === "incident-review" && incidentReview) {
        return <IncidentReview review={incidentReview} error={error} onUpdate={setIncidentReview}
          onRetry={() => startAnalysis(null, tableReview?.decision || null, true)}
          onBack={backToUploadedFiles} />;
      }

      if (uploadingProjectId === selectedProjectId && screen === "table-review" && tableReview) {
        return <FoundationTableReview review={tableReview} error={error}
          onConfirm={(decision) => startAnalysis(null, decision, true)}
          onBack={backToUploadedFiles} />;
      }

      if (uploadingProjectId === selectedProjectId && screen === "geometry-review" && geometryReview) {
        const GeometryReviewComponent = geometryReview.tipo === "cimientos_corridos_geometria_distribuida"
          ? ContinuousFoundationReview
          : FoundationGeometryReview;
        return <GeometryReviewComponent
          review={geometryReview}
          projectId={project.id}
          error={error}
          onConfirm={(decision) => startAnalysis(null, null, true, decision)}
          onBack={() => {
            setGeometryReview(null);
            setScreen("routing-review");
            setActiveView("documentation");
          }}
        />;
      }

      if (activeView === "documentation" && project.clasificacionDocumental && uploadingProjectId !== selectedProjectId) {
        return <DocumentRoutingReview key={project.id} projectId={project.id} onReviewUpdated={review => updateDocumentReview(project.id, review)} review={project.clasificacionDocumental}
          onBack={() => handleUploadForProject(project.id)} />;
      }

      // Upload
      if (
        uploadingProjectId === selectedProjectId &&
        screen === "upload"
      ) {
        return (
          <Upload
            files={files}
            error={error}
            backendStatus={backendStatus}
            backendError={backendError}
            onFilesSelected={handleFilesSelected}
            onClear={clearFile}
            onStart={startAnalysis}
          />
        );
      }

      if (
        uploadingProjectId === selectedProjectId &&
        screen === "routing-review" &&
        routingReview
      ) {
        return (
          <DocumentRoutingReview
            key={JSON.stringify(
              routingReview.asignaciones_sugeridas || {}
            )}
            projectId={project.id}
            onReviewUpdated={review => updateDocumentReview(project.id, review)}
            files={files}
            review={routingReview}
            error={error}
            onConfirm={() => startAnalysis(null, null, true)}
            onBack={backToUploadedFiles}
          />
        );
      }

      // Processing
      if (
        uploadingProjectId === selectedProjectId &&
        screen === "processing"
      ) {
        return (
          <Processing
            progress={progress}
            documentCount={files.length}
          />
        );
      }

      // Results
      if (activeView === "results") {
        const ResultsComponent = visibleResults?.tipologia_fundacion === "cimientos_corridos"
          ? ContinuousFoundationResults
          : Results;
        return (
          <ResultsComponent
            results={visibleResults}
            error={error}
            onResultsChange={(updated) => {
              setCurrentResults(updated);
              setCurrentResultsProjectId(selectedProjectId);
              setAnalyses((items) => items.map((item) => item.backendId === updated.analisis_id
                ? {
                    ...item,
                    resultado: updated,
                    volume: Number(updated.volumen_hormigon_m3 || 0),
                    geometricVolume: updated.volumen_cimientos_corridos_m3 ?? updated.volumen_hormigon_m3,
                  }
                : item));
            }}
            onNewAnalysis={() =>
              handleUploadForProject(
                selectedProjectId
              )
            }
            onBack={backToAnalyses}
            onDownload={() => downloadResults(visibleResults)}
          />
        );
      }

      if (activeView === "model-3d") {
  return (
    <Motor3D
      key={`${selectedProjectId}:${visibleResults?.analisis_id ?? "sin-analisis"}`}
      project={project}
      results={visibleResults}
      onBack={() => navigate("results")}
    />
  );
}

      // Análisis
      if (activeView === "analysis") {
  return (
    <Analyses
      analyses={analyses}
      projects={projects}
      selectedProjectId={selectedProjectId}
      error={error}
      onOpenAnalysis={openAnalysis}
      onNewAnalysis={() => handleUploadForProject(selectedProjectId)}
    />
  );
}

      // Documentación
      if (activeView === "documentation") {
        return (
          <Upload
            files={files}
            error={error}
            backendStatus={backendStatus}
            backendError={backendError}
            onFilesSelected={handleFilesSelected}
            onClear={clearFile}
            onStart={startAnalysis}
          />
        );
      }

      // Reportes
      if (activeView === "reports") {
        return (
          <PlaceholderView
            title="Reportes"
            description={`Los reportes de ${project.name} estarán disponibles en esta sección.`}
            icon="report"
          />
        );
      }

      // Resumen
      return (
        <ProjectDetail
          project={project}
          analyses={analyses}
          onBack={backToProjects}
          onUpload={() =>
            handleUploadForProject(project.id)
          }
          onOpenAnalysis={() => {
            setActiveView("analysis");
            setScreen("idle");
          }}
        />
      );
    }

    // -------------------------------------------------------
    // FUERA DE PROYECTO
    // -------------------------------------------------------

    if (activeView === "dashboard") {
      return <Dashboard projects={projects} analyses={analyses}
        onNewAnalysis={() => navigate("projects")} onOpenProject={openProject} />;
    }

    if (activeView === "projects") {
      return (
        <Projects
          projects={projects}
          analyses={analyses}
          onNewProject={() =>
            setShowNewProject(true)
          }
          onOpenProject={openProject}
        />
      );
    }

    return (
      <PlaceholderView
        title="Seleccioná un proyecto"
        description="Esta sección está disponible dentro de un proyecto."
        icon="folder"
        action="Ver proyectos"
        onAction={() => navigate("projects")}
      />
    );
  }

  // =========================================================
  // APP
  // =========================================================

  return (
    <div className="flex min-h-screen bg-mist">
      <Sidebar
        activeView={activeView === "results" ? "analysis" : activeView}
        onNavigate={navigate}
        selectedProject={selectedProject}
        backendStatus={backendStatus}
        onLogout={handleLogout}
      />

      <div className="min-w-0 flex-1">
        {storageError && <section role="alert" className="m-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <p className="font-bold">No se pudo guardar el historial en este navegador.</p>
          <p>Podés seguir trabajando en esta sesión. Descargá un respaldo antes de cerrar o recargar. {storageError}</p>
          <div className="mt-3 flex gap-3">
            <button className="rounded border px-3 py-2" onClick={() => downloadWorkspace({ projects, analyses })}>Descargar respaldo</button>
            <button className="rounded border px-3 py-2" onClick={() => { setStorageWritable(true); setSaveAttempt((n) => n + 1); }}>Reintentar guardado</button>
          </div>
        </section>}
        {renderContent()}
      </div>
    </div>
  );
}

export default App;
