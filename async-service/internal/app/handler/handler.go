package handler

import (
    "github.com/gin-gonic/gin"
    "net/http"
    "async-service/internal/app/service"
)

type Handler struct {
    service *service.Service
}

func NewHandler(service *service.Service) *Handler {
    return &Handler{
        service: service,
    }
}

func (h *Handler) CalculatePopulation(c *gin.Context) {
    // Определяем структуру запроса
    type RequestData struct {
        ApplicationID int                     `json:"application_id" binding:"required"`
        Token         string                  `json:"token" binding:"required"`
        TerritoryArea float64                 `json:"territory_area" binding:"required"`
        Orders        []service.OrderData     `json:"orders" binding:"required"`
    }
    
    var request RequestData
    
    if err := c.ShouldBindJSON(&request); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{
            "error": "Invalid request format",
            "details": err.Error(),
        })
        return
    }
    
    // Проверяем токен (псевдо-авторизация)
    if !h.service.ValidateToken(request.Token) {
        c.JSON(http.StatusUnauthorized, gin.H{
            "error": "Invalid token",
        })
        return
    }
    
    // Запускаем асинхронный расчет в отдельной горутине
    go h.service.CalculatePopulationAsync(
        request.ApplicationID,
        request.TerritoryArea,
        request.Orders,
    )
    
    // Немедленно возвращаем ответ
    c.JSON(http.StatusAccepted, gin.H{
        "message": "Population calculation initiated",
        "application_id": request.ApplicationID,
        "status": "processing",
        "estimated_delay": "5-10 seconds",
    })
}

func (h *Handler) HealthCheck(c *gin.Context) {
    c.JSON(http.StatusOK, gin.H{
        "status": "ok",
        "service": "async-population-calculator",
        "version": "1.0.0",
    })
}