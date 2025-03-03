job "fun-app" {
  datacenters = ["dc1"]
  type = "service"

  group "api-group" {
    count = 2  # Run the service on two clients for redundancy

    task "fun-api-task" {
      driver = "docker"

      config {
        image = "artemsoze/fun-app:latest"
        ports = ["http"]
      }

      resources {
        cpu    = 500  # 500 MHz CPU
        memory = 128  # 256 MB RAM
      }
    }

    network {
      port "http" {
        to = 3000  # Internal Docker port
        static = 80  # External port (exposed to users)
      }
    }

    service {
      name = "fun-app"
      port = "http"

      check {
        type     = "http"
        path     = "/health"
        interval = "10s"
        timeout  = "2s"
      }
    }
  }
}

