Feature: Universo inicial de companhias monitoradas

  Para analisar informações do mercado financeiro brasileiro
  Como usuário do BR Financial AI
  Quero identificar as companhias inicialmente monitoradas pelos seus tickers

  Scenario Outline: Identificar companhia por ticker
    Given que existe um universo inicial de companhias monitoradas
    When eu consulto o ticker "<ticker>"
    Then a companhia identificada deve ser "<company>"

    Examples:
      | ticker | company   |
      | PETR3  | Petrobras |
      | PETR4  | Petrobras |
      | BBDC3  | Bradesco  |
      | BBDC4  | Bradesco  |
      | VALE3  | Vale      |