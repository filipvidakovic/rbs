use axum::{routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::UnixStream;
use tokio::process::Command;
use serde_json::json;
use base64::{Engine as _, engine::general_purpose::STANDARD as base64_std};
use std::fs;

#[derive(Deserialize, Debug)]
pub struct ExecutionRequest {
    pub function_hash: String,
    pub code: String,
    pub requirements: Option<String>,
}

#[derive(Serialize)]
pub struct ExecutionResponse {
    pub status: String,
    pub output: Option<String>,
    pub error: Option<String>,
}

#[tokio::main]
async fn main() {
    let app = Router::new().route("/api/v1/execute", post(handle_execute));
    let addr = SocketAddr::from(([127, 0, 0, 1], 8081));
    println!("🔥 Firecracker Orkestrator API pokrenut na http://{}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn handle_execute(Json(payload): Json<ExecutionRequest>) -> Json<ExecutionResponse> {
    println!("\n[Orkestrator] Primljen zahtev za izvršavanje funkcije: {}", payload.function_hash);
    
    let mut deps_b64 = String::new();
    
    // 1. Priprema zavisnosti (Ako ih ima)
    if let Some(reqs) = payload.requirements {
        if !reqs.trim().is_empty() {
            println!("[Orkestrator] Pronađene zavisnosti, preuzimam preko pip-a...");
            let _ = fs::remove_dir_all("./temp_deps");
            fs::create_dir_all("./temp_deps").unwrap();
            fs::write("./temp_deps/requirements.txt", reqs).unwrap();
            
            let pip_status = Command::new("python3")
                .args(["-m", "pip", "install", "-r", "./temp_deps/requirements.txt", "--target", "./temp_deps"])
                .output()
                .await;

            match pip_status {
                Ok(output) if output.status.success() => {
                    // BUGFIX: Umesto nepouzdanog sistemskog zip-a, koristimo ugrađenu Python skriptu na hostu za pravljenje ZIP-a
                    let _ = Command::new("python3")
                        .args(["-c", "import shutil; shutil.make_archive('./deps', 'zip', './temp_deps')"])
                        .output()
                        .await;
                        
                    if let Ok(zip_data) = fs::read("./deps.zip") {
                        deps_b64 = base64_std.encode(zip_data);
                        println!("[Orkestrator] Zavisnosti uspešno spakovane u Base64.");
                    } else {
                        println!("[Orkestrator] GREŠKA: Fajl ./deps.zip nije pronađen na disku nakon pakovanja!");
                    }
                }
                _ => {
                    return Json(ExecutionResponse {
                        status: "ERROR".to_string(),
                        output: None,
                        error: Some("Failed to install dependencies on host".to_string()),
                    });
                }
            }
        }
    }

    // 2. Kreiranje JSON-a za Firecracker agenta unutar mašine
    let agent_payload = json!({
        "code": payload.code,
        "deps_b64": deps_b64
    });
    
    let mut data_to_send = serde_json::to_string(&agent_payload).unwrap();
    data_to_send.push_str("<EOF>");

    // 3. Povezivanje na Firecracker mašinu preko Unix Socketa
    let socket_path = "../firecracker-test/v.sock"; 
    println!("[Orkestrator] Povezujem se na Firecracker mašinu...");
    
    match UnixStream::connect(socket_path).await {
        Ok(mut stream) => {
            if stream.write_all(b"CONNECT 5000\n").await.is_err() {
                return Json(ExecutionResponse {
                    status: "ERROR".to_string(),
                    output: None,
                    error: Some("Failed to talk to Firecracker proxy".to_string()),
                });
            }
            
            let mut buf = [0; 1024];
            let _ = stream.read(&mut buf).await;
            
            println!("[Orkestrator] Upucavam kod u izolovanu mašinu...");
            stream.write_all(data_to_send.as_bytes()).await.unwrap();
            
            println!("[Orkestrator] Čekam rezultat izvršavanja...");
            let mut result = String::new();
            stream.read_to_string(&mut result).await.unwrap();
            
            println!("[Orkestrator] Izvršavanje uspešno završeno!");
            Json(ExecutionResponse {
                status: "SUCCESS".to_string(),
                output: Some(result),
                error: None,
            })
        },
        Err(e) => {
            println!("[Orkestrator] Greška: Mašina nije dostupna na putanji {}. Da li je Firecracker upaljen?", socket_path);
            Json(ExecutionResponse {
                status: "ERROR".to_string(),
                output: None,
                error: Some(format!("Firecracker VM unreachable: {}", e)),
            })
        }
    }
}