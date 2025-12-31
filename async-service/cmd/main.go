package main

import (
    "log"
    "os"
    "async-service/internal/app/handler"
    "async-service/internal/app/service"
    "github.com/gin-gonic/gin"
    "github.com/joho/godotenv"
)

func main() {
    // Загружаем переменные окружения
    if err := godotenv.Load(); err != nil {
        log.Printf("Warning: .env file not found, using defaults")
    }
    
    // Создаем сервис
    svc := service.NewService()
    
    // Создаем обработчик
    h := handler.NewHandler(svc)
    
    // Настраиваем Gin
    r := gin.Default()
    
    // Добавляем CORS middleware
    r.Use(func(c *gin.Context) {
        c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
        c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS, PUT, DELETE")
        c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CSRF-Token")
        c.Writer.Header().Set("Access-Control-Expose-Headers", "Content-Length")
        c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
        
        if c.Request.Method == "OPTIONS" {
            c.AbortWithStatus(200)
            return
        }
        
        c.Next()
    })
    
    // Добавляем обработчики
    r.POST("/calculate_population", h.CalculatePopulation)
    r.GET("/health", h.HealthCheck)
    
    // Запускаем сервер
    port := os.Getenv("GO_PORT")
    if port == "" {
        port = "8081"
    }
    
    log.Printf("🚀 Starting async service on port %s", port)
    log.Printf("📊 Django URL: %s", svc.DjangoURL)
    
    if err := r.Run(":" + port); err != nil {
        log.Fatal(err)
    }
}