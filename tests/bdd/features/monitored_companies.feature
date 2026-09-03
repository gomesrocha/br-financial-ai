Feature: Universo inicial de companhias monitoradas

  Para analisar informações do mercado financeiro brasileiro
  Como usuário do BR Financial AI
  Quero identificar as companhias inicialmente monitoradas pelos seus tickers

  Scenario Outline: Identificar companhia por ticker
    Given que existe um universo inicial de companhias monitoradas
    When eu consulto o ticker "<ticker>"
    Then a companhia identificada deve possuir o código CVM "<cvm_code>"

    Examples:
      | ticker | cvm_code |
      | PETR3  | 9512     |
      | PETR4  | 9512     |
      | BBDC3  | 906      |
      | BBDC4  | 906      |
      | VALE3  | 4170     |