package service

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "math/rand"
    "net/http"
    "os"
    "strconv"
    "time"
)

type Service struct {
    DjangoURL    string
    authToken    string
    minDelay     int
    maxDelay     int
}

func NewService() *Service {
    return &Service{
        DjangoURL: getEnv("DJANGO_URL", "http://localhost:8000"),
        authToken: getEnv("ASYNC_SERVICE_TOKEN", "my-secret-token-12345"),
        minDelay:  getEnvAsInt("DELAY_MIN", 5),
        maxDelay:  getEnvAsInt("DELAY_MAX", 10),
    }
}

func (s *Service) ValidateToken(token string) bool {
    return token == s.authToken
}

func (s *Service) CalculatePopulationAsync(applicationID int, territoryArea float64, orders []OrderData) {
    // Имитируем долгий расчет (5-10 секунд)
    delay := s.minDelay + rand.Intn(s.maxDelay-s.minDelay+1)
    fmt.Printf("Starting calculation for application %d, will take %d seconds\n", applicationID, delay)
    
    time.Sleep(time.Duration(delay) * time.Second)
    
    // Выполняем расчет по формуле из лабораторной
    totalPopulation := s.calculateTotalPopulation(territoryArea, orders)
    
    // Добавляем случайное отклонение (±10%) для имитации уточненного расчета
    rand.Seed(time.Now().UnixNano())
    deviation := 0.9 + rand.Float64()*0.2 // от 0.9 до 1.1
    finalPopulation := int(float64(totalPopulation) * deviation)
    
    fmt.Printf("Calculated population for app %d: %d people\n", applicationID, finalPopulation)
    
    // Пытаемся отправить результат обратно в Django (3 попытки)
    maxRetries := 3
    for i := 1; i <= maxRetries; i++ {
        err := s.sendResultToDjango(applicationID, finalPopulation)
        if err == nil {
            fmt.Printf("Successfully sent result for application %d on attempt %d\n", applicationID, i)
            return
        }
        fmt.Printf("Attempt %d failed for application %d: %v\n", i, applicationID, err)
        if i < maxRetries {
            time.Sleep(time.Duration(i*2) * time.Second) // Экспоненциальная задержка
        }
    }
    fmt.Printf("Failed to send result for application %d after %d attempts\n", applicationID, maxRetries)
}

func (s *Service) calculateTotalPopulation(territoryArea float64, orders []OrderData) int {
    total := 0
    
    for _, order := range orders {
        // Рассчитываем численность для каждой услуги
        // Преобразуем float в int для расчета
        buildingDensity := int(order.BuildingDensity)
        peoplePerBuilding := int(order.PeoplePerBuilding)
        
        if buildingDensity > 0 && peoplePerBuilding > 0 {
            population := territoryArea * float64(buildingDensity) * float64(peoplePerBuilding)
            total += int(population)
        }
    }
    
    return total
}

func (s *Service) sendResultToDjango(applicationID int, population int) error {
    // Правильный URL для Django
    url := fmt.Sprintf("%s/api/density_calculations/%d/async_result/", s.DjangoURL, applicationID)
    
    fmt.Printf("Sending result to Django: %s\n", url)
    
    data := map[string]interface{}{
        "async_population":   population,
        "calculation_status": "completed",
        "calculation_method": "async_refined",
        "auth_token":         "django-secret-token-67890",
    }
    
    jsonData, err := json.Marshal(data)
    if err != nil {
        fmt.Printf("Error marshaling data: %v\n", err)
        return err
    }
    
    fmt.Printf("Payload: %s\n", string(jsonData))
    
    req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
    if err != nil {
        fmt.Printf("Error creating request: %v\n", err)
        return err
    }
    
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("User-Agent", "Async-Go-Service/1.0")
    
    client := &http.Client{
        Timeout: 30 * time.Second,
    }
    
    resp, err := client.Do(req)
    if err != nil {
        fmt.Printf("Error sending request: %v\n", err)
        return err
    }
    defer resp.Body.Close()
    
    body, _ := io.ReadAll(resp.Body)
    fmt.Printf("Response status: %d, body: %s\n", resp.StatusCode, string(body))
    
    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("status code: %d, body: %s", resp.StatusCode, string(body))
    }
    
    fmt.Printf("Successfully sent async result for application %d: %d people\n", applicationID, population)
    return nil
}

// Структура для данных услуги - изменяем на float64 для совместимости
type OrderData struct {
    BuildingDensity   float64 `json:"building_density"`
    PeoplePerBuilding float64 `json:"people_per_building"`
}

// Вспомогательные функции
func getEnv(key, defaultValue string) string {
    if value := os.Getenv(key); value != "" {
        return value
    }
    return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
    if value := os.Getenv(key); value != "" {
        if intValue, err := strconv.Atoi(value); err == nil {
            return intValue
        }
    }
    return defaultValue
}