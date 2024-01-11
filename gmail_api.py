import os
import sys
import base64
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from pathlib import Path
from datetime import datetime, timedelta, timezone
#import logging
import urllib
from urllib.request import urlopen
import ctypes

"""
Auto downloader de anexos para Gmail - Versão 1.2.1

Copyright (c) 2024 Bruno Benvenutti

Permissão é concedida, gratuitamente, a qualquer pessoa que obtenha uma cópia deste software e arquivos de
documentação associados (o "BaixarAnexosGmail"), para negociar no Programa sem restrições, incluindo, sem limitação, 
os direitos de usar, copiar, modificar, mesclar, publicar, distribuir, sublicenciar e/ou vender cópias do Programa,
e permitir que as pessoas a quem o Programa é fornecido o façam, sujeitas às seguintes condições:

O cabeçalho acima e este aviso de permissão devem ser incluídos em todas as cópias ou partes substanciais do 
Programa.

O PROGRAMA É FORNECIDO "COMO ESTÁ", SEM GARANTIA DE QUALQUER TIPO, EXPRESSA OU IMPLÍCITA, INCLUINDO, MAS NÃO 
SE LIMITANDO ÀS GARANTIAS DE COMERCIALIZAÇÃO, ADEQUAÇÃO A UM PROPÓSITO ESPECÍFICO E NÃO VIOLAÇÃO. EM NENHUM CASO 
OS AUTORES OU TITULARES DE DIREITOS AUTORAIS SERÃO RESPONSÁVEIS POR QUALQUER RECLAMAÇÃO, DANOS OU OUTRA 
RESPONSABILIDADE, SEJA EM AÇÃO DE CONTRATO, DELITO OU DE OUTRA FORMA, DECORRENTE, FORA DE OU EM CONEXÃO COM O 
PROGRAMA OU O USO OU OUTRAS NEGOCIAÇÕES NO PROGRAMA.
"""

# contact: brkas_dev@proton.me

# Configurações
user = Path.home()
SCOPES = ['https://mail.google.com/']  # Acesso total ao Gmail do usuário
# CREDENTIALS_FILE = 'credentials.json' # credentials.json path
# QUERY = 'is:unread has:attachment'  # Filtro para buscar emails não lidos com anexos
SAVE_DIR = os.path.join('config.txt')

'''Desabilita o quick edit mode, que faz com que a execução do script seja pausada toda vez que o prompt
recebe um click de mouse. O código abaixo resolve esse problema.'''
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Constants
ENABLE_QUICK_EDIT_MODE = 0x0040

# Get console mode
handle = kernel32.GetStdHandle(-10)  # -10 corresponde à saída padrão
mode = ctypes.c_uint()
kernel32.GetConsoleMode(handle, ctypes.byref(mode))

# Disable Quick Edit Mode
mode.value &= ~ENABLE_QUICK_EDIT_MODE
kernel32.SetConsoleMode(handle, mode)
'''END QUICK EDIT MODE DISABLE SCRIPT'''

# A primeira vez que o programa for iniciado, será solicitado a escolha de um diretório
if not os.path.exists(SAVE_DIR):
    dir = str(input("Δ Essa é sua primeira vez executando o programa, digite o caminho do diretório onde os anexos "
                    "serão salvos: "))
    print("")
    auto_clear = int(input("Δ Deseja ativar a função de limpar emails lidos da caixa de entrada automaticamente?\n"
                           "(1) Sim\n"
                           "(2) Não\n"
                           "Δ Digite: "))
    if auto_clear == 1:
        date_interval = int(input("Δ A cada quantos dias deseja fazer a limpeza da Caixa de Entrada(INBOX)?\n"
                                  "Δ Digite: "))
    else:
        date_interval = 99999

    print("")
    with open(SAVE_DIR, 'w') as diretorio:
        diretorio.write(f"path={dir}\n")
        diretorio.write(f"auto_clear={'TRUE' if auto_clear == 1 else 'FALSE'}\n")
        diretorio.write(f"auto_clear_date={datetime.now().date()}\n")
        diretorio.write(f"date_interval={date_interval}")
    print("Δ Configurações salvas em config.txt.")
    if not os.path.exists(dir):
        try:
            print(f"Δ Criando diretório: {dir}")
            os.makedirs(dir)
        except Exception as e:
            print(f"Δ Erro ao criar diretorio: {dir}")
            print(f"Erro: {e}")
    else:
        print("Δ Diretório já existe.")

else:
    print("Δ Configurações carregadas de config.txt.")


# 1) Autenticar fazendo login no google
def gerar_token():
    creds = None

    try:
        # Obtenha o caminho do diretório do script principal
        script_dir = getattr(sys, '_MEIPASS', os.path.abspath("."))
        # Construa o caminho relativo ao diretório do script principal
        credentials_path = os.path.join(script_dir, 'credentials.json')
        print(f"credentials_path: {credentials_path}")
    except Exception as e:
        credentials_path = os.path.join("credentials.json")
        if credentials_path:
            print(f"Caminho do credentials.json: {credentials_path}")
        else:
            print(f"Erro: {e}")

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)

    email_associado = obter_email(creds)

    if email_associado:
        print(f'Δ O e-mail associado à conta é: {email_associado}')
        time.sleep(3)
    else:
        print('Δ Não foi possível obter o endereço de e-mail.')
        time.sleep(3)

    return creds


def obter_email(credentials):
    service = build('gmail', 'v1', credentials=credentials)
    info_conta = service.users().getProfile(userId='me').execute()
    email = info_conta.get('emailAddress')
    return email


def listar_contas():
    diretorio = os.getcwd()
    palavra_de_busca = 'token'
    arquivos = os.listdir(diretorio)

    # Filtra os arquivos que contêm a palavra desejada no nome
    arquivos_com_palavra = [arquivo for arquivo in arquivos if palavra_de_busca in arquivo]

    contas = arquivos_com_palavra
    return contas


def verificar_conta(arquivo_escolhido):
    creds = None

    # O arquivo token.json armazena as credenciais do usuário e é criado automaticamente após a primeira execução
    if os.path.exists(arquivo_escolhido):
        creds = Credentials.from_authorized_user_file(arquivo_escolhido)

    # Se não houver credenciais válidas disponíveis, solicita que o usuário faça login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print(f"Δ (Refresh) Atualizando token: {arquivo_escolhido}")
                refresh = creds.refresh(Request())
                time.sleep(3)
                if refresh:
                    print(f"Δ Token {arquivo_escolhido} atualizado com sucesso ")
                time.sleep(3)
            except Exception as e:
                print(f"Δ Erro ao dar Refresh no token na conta: {arquivo_escolhido}\n"
                      f"Δ Erro: {e}")
                time.sleep(3)

        else:
            credentials = gerar_token()  # Pega o valor de creds e joga na variavel "credentials"
            email = obter_email(
                credentials)  # Constroi a API com build usando a variavel credentials para obter o email

            # Salve as credenciais para a próxima vez
            salvar_credencial_unica(credentials, email)  # Com o valor das duas variaveis acima, salva o token em JSON

    try:
        # Construa o serviço Gmail
        service = build('gmail', 'v1', credentials=creds)
        print("Δ API do Gmail construída com sucesso.")
        return service
    except Exception as e:
        print(f"Δ Erro ao construir o API do Gmail: {e}")
        return None


def salvar_credencial_unica(credentials, email):
    email_json = str(email + '_token.json')

    with open(email_json, 'w') as token_file:
        token_file.write(credentials.to_json())

    print(f"Δ Token para {email} criado com sucesso")
    time.sleep(3)

    return email_json

def marcar_como_lido(service, user_id, message_id):
    try:
        service.users().messages().modify(userId=user_id, id=message_id, body={'removeLabelIds': ['UNREAD']}).execute()
        print("Δ E-mail marcado como lido")
        time.sleep(2)
    except Exception as e:
        print(f"Δ Erro ao marcar email como lido: {e}")
        time.sleep(30)

def baixar_anexos(service, user_id, message_id, diretorio):
    try:
        message = service.users().messages().get(userId=user_id, id=message_id).execute()

        detalhes_email = {'id': message['id'], 'snippet': message['snippet'], 'labelIds': message['labelIds']}
        print(f"\n"
              f"Δ Detalhes do email: \n"
              f"ID: {detalhes_email['id']}\n"
              f"Resumo: {detalhes_email['snippet'][:25]}\n"
              f"Marcadores: {detalhes_email['labelIds']}"
              f"\n")

        for part in message['payload']['parts']:
            if 'filename' in part and part['filename']:
                nome_anexo = part['filename']

                # Construir o novo nome do arquivo com data e hora
                timestamp = datetime.fromtimestamp(int(message['internalDate']) / 1000.0)
                timestamp_str = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
                novo_nome_arquivo = f"{timestamp_str}_{nome_anexo}"

                # Obter os dados binários do anexo
                if 'body' in part and 'attachmentId' in part['body']:
                    attachment = service.users().messages().attachments().get(
                        userId=user_id,
                        messageId=message_id,
                        id=part['body']['attachmentId']
                    ).execute()

                    dados_base64 = attachment['data']
                    dados_bytes = base64.urlsafe_b64decode(dados_base64)

                    # Construir o caminho completo para salvar o anexo
                    full_path = os.path.join(diretorio, novo_nome_arquivo)

                    # Decodificar e salvar o conteúdo do anexo
                    with open(full_path, 'wb') as arquivo:
                        arquivo.write(dados_bytes)
                        print(f"Δ Anexo '{nome_anexo}' baixado com sucesso.\n"
                              f"Δ Salvo em: {full_path}")

        return True

    except Exception as e:
        error_mails = os.path.join("error_mails.txt")

        # Verifica se o arquivo existe, e cria se não existir
        if not os.path.exists(error_mails):
            with open(error_mails, 'w'):
                pass

        print(f"Δ Erro ao baixar anexo: {e}")
        with open(error_mails, 'a') as relatorio:
            relatorio.write(f"Erro ao baixar anexo: {e}\n")
            relatorio.write(f"Data e hora do erro: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            relatorio.write(f"E-mail ID: {detalhes_email['id']}\n")
            relatorio.write("------------------------------------------------------------------------\n")
            relatorio.write("")

        c = checar_conexao()
        while not c:
            c = checar_conexao()
            print("Sem conexão com a internet. Tentando reconectar...")
            time.sleep(5)
        print("Conexão estabelecida. Retomando download...")
        time.sleep(5)
        return False


# Calcula o tamanho da lista de emails com anexo, em bytes
def calcular_tamanho_anexos(service, message_id):
    total_attachment_size = 0
    attachment_metadata = service.users().messages().attachments().list(userId='me', messageId=message_id).execute()

    if 'attachments' in attachment_metadata:
        for attachment in attachment_metadata['attachments']:
            attachment_details = service.users().messages().attachments().get(userId='me', messageId=message_id,
                                                                              id=attachment['id']).execute()
            attachment_size = len(attachment_details['data'])  # O tamanho do anexo em bytes
            total_attachment_size += attachment_size

    return total_attachment_size


def search_messages(service, query):
    result = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
    messages = []
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
        result_size = result.get('resultSizeEstimate', [])  # em desuso
    return messages


def date_to_seconds(date):
    dt = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.timestamp()


def filtro(service):
    data_hoje = datetime.now(timezone(timedelta(hours=-3))).replace(hour=0, minute=0, second=0, microsecond=0)

    data_formatada = data_hoje.strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'

    seconds = date_to_seconds(data_formatada)

    # Filtrando e buscando mensagens
    query = f"is:unread after:{int(seconds)} has:attachment"  # Busca somente mensagens não lidas que possuam anexo
    resultados = search_messages(service, query)

    return resultados


def deletar_conta(num, gmails):
    try:
        arquivo = gmails[num - 1]
        os.remove(arquivo)
        return True
    except Exception as e:
        print(f"Δ Erro ao deletar {arquivo}: {e}")
        time.sleep(5)
        return False


def pasta_hoje_path(data_hoje):
    # Retorna o path de salvamento dos anexos definido pelo usuário e salvo  em "config.txt" mais uma pasta
    # noemada com a data atual
    caminho = ler_config("path=")

    formatted_date = data_hoje.strftime("%d-%m-%Y")

    novo_path = str(caminho + f"\{formatted_date}")

    return novo_path


def criando_pasta_hoje(nome_pasta):
    # Cria a pasta nomeada com o dia de hoje
    if not os.path.exists(nome_pasta):
        try:
            os.makedirs(nome_pasta)
            print("Δ Pasta de hoje criada com sucesso. Seus anexos baixados hoje seram salvos nela.")
            time.sleep(10)
            return True
        except Exception as e:
            print(f"Δ Erro a criar a pasta do dia de hoje: {e}")
            time.sleep(60)
            return False
    else:
        print("Δ Pasta de hoje já existe.")
        time.sleep(5)
        return False


def comparar_datas(data_hoje):
    if data_hoje != datetime.now().date():
        print("Δ A data de hoje mudou.")
        time.sleep(5)
        return True
    else:
        return False


def checar_conexao():
    try:
        urlopen('https://www.google.com', timeout=2)
        return True
    except urllib.error.URLError:
        return False


def reiniciar_programa():
    python = sys.executable
    os.execl(python, python, *sys.argv)


def contador_segundos(tempo_total, texto):
    for segundos in range(tempo_total, 0, -1):
        print(f"Δ Aguardando {segundos} segundos {texto}", end='\r')
        time.sleep(1)

    # Limpar a linha após a contagem regressiva
    print(" " * len(f"Δ Aguardando {tempo_total} segundos {texto}"), end='\r', flush=True)

def limpar_inbox(service):
    # Excluir emails lidos da caixa de entrada
    query = f"is:read"
    messages = search_messages(service, query)
    quantidade_email = len(messages)
    print(f"Δ Emails a serem excluidos: {quantidade_email}")

    if messages:
        for message in messages:
            try:
                service.users().messages().delete(userId='me', id=message['id']).execute()
                print(f"Δ Mensagem excluida com sucesso. Message ID: {message['id']}")
                time.sleep(2)
                return True
            except Exception as e:
                print(f"Δ Erro ao limpar Caixa de entrada: {e}")
    else:
        print("Δ Não foram encontrados emails a serem excluidos.")
        print("")
        time.sleep(3)

def ler_config(parametro):
    # Formato do parametro 'texto='
    with open(SAVE_DIR, 'r') as config:
        linhas = config.readlines()
        result = None
        for linha in linhas:
            if linha.startswith(parametro):
                result = linha.split('=')[1].strip()
                return result
        return result

def escrever_config(p1, p2):
    try:
        with open(SAVE_DIR, 'r') as config:
            d = config.readlines()
    except FileNotFoundError:
        return []

    d.append(f'{p1}={p2}\n')

    with open(SAVE_DIR, 'w') as config:
        config.writelines(d)

def calcular_diferenca():
    data_str1 = datetime.now().date().strftime("%Y-%m-%d")
    data_str2 = ler_config('auto_clear_date=')
    try:
        data1 = datetime.strptime(data_str1, "%Y-%m-%d")
        data2 = datetime.strptime(data_str2, "%Y-%m-%d")

        dif_date = data1 - data2
    except Exception as e:
        print(f"Erro em calcular_diferenca(): {e}")
    return dif_date


def main():
    # Configuração do logger que é uma biblioteca para salvar erros em um arquivo para que eu possa consultar depois
    # logging.basicConfig(filename='log.txt', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

    data_hoje = datetime.now().date()  # Pega a data de hoje para comparação futura

    diretorio = ler_config("path=")

    if os.path.exists(diretorio):
        print("")
        print("Δ Diretório padrão configurado: ", diretorio)
        time.sleep(2)
    else:
        print("Δ Erro no diretório. Necessário especificar o caminho novamente.")
        os.remove(SAVE_DIR)
        print("Δ Arquivo config.txt removido. Reiniciando o programa para escolher um novo diretório.")
        time.sleep(5)
        try:
            reiniciar_programa()
        except:
            exit()

    print("Δ Após escolher uma conta, o download dos anexos das proximas contas será feito automaticamente \n"
          "em todos emails não lidos que possuam um anexo.")
    time.sleep(2)

    today_folder = pasta_hoje_path(data_hoje)
    criando_pasta_hoje(today_folder)
    diretorio_hoje = today_folder
    print(f"Δ Salvando anexos de hoje em: {diretorio_hoje}\n"
          f"")
    time.sleep(3)

    # Carregar auto_clear
    auto_clear = ler_config('auto_clear=')

    while True:
        try:
            n = 0
            gmails = listar_contas()
            print("Δ Escolha o número da conta na qual deseja iniciar o download dos anexos: ")

            for i, arquivo in enumerate(gmails, start=1):
                print(f"({i}) {arquivo}")
            print("")

            numero_escolhido = int(input("Δ Outras opções:\n"
                                         "( 0 ) Baixar anexos de uma única conta (Monitora uma unica conta) ("
                                         "Funcionalidade indisponível) \n"  # Implementar
                                         "(-1 ) Adicionar nova conta \n"
                                         "(-2 ) Escolher data, hora e ordem em que baixar os anexos "
                                         "(Funcionalidade indisponÍvel) \n"  # Implementar
                                         "(-3 ) Deletar uma conta \n"
                                         "(-4 ) Trocar o diretório de salvamento dos anexos\n"
                                         "(-5 ) Limpar e-mails lidos da Caixa de Entrada(INBOX)\n"
                                         "( ? ) Digite qualquer letra(STRING) para encerrar o programa \n"
                                         "Δ Digite: "))
            print('')
            time.sleep(3)

            if numero_escolhido >= 1:
                escolher_ordem = int(input(
                    "Δ Qual a ordem em que você quer baixar os anexos? \n"
                    "1) (antigo-->recente) Do mais antigo para o mais recente \n"
                    "2) (recente-->antigo) Do mais recente para o mais antigo \n"
                    "Δ Digite: "))
                print("")
                if escolher_ordem == 1:
                    ordem = -1  # Começa no ultimo item da lista
                elif escolher_ordem == 2:
                    ordem = 0  # Começa no primeiro item da lista

            os.system('cls' if os.name == 'nt' else 'clear')  # Limpa o console

            while True:
                if 1 <= numero_escolhido <= len(gmails):
                    arquivo = gmails[numero_escolhido - 1]
                    try:
                        service = verificar_conta(arquivo)
                    except Exception as e:
                        print("")
                        print(f"Δ Erro ao contruir a api: {e}")
                        print("")
                        time.sleep(5)
                    remover_string = '_token.json'
                    nome_arquivo = arquivo.replace(remover_string, "")
                    print("")
                    print(f"Δ Pesquisando em: {nome_arquivo}")
                    print("")
                    time.sleep(2)

                    # Limpar automaticamente emails lidos da caixa de entrada
                    dif_date = calcular_diferenca()
                    intervalo_data = ler_config('date_interval=')
                    intervalo_data = timedelta(days=int(intervalo_data))

                    if auto_clear == 'TRUE' and dif_date > intervalo_data:
                        print(f"Δ Limpando emails lidos da caixa de entrada de {nome_arquivo}")
                        print("")
                        clear = limpar_inbox(service)
                        if clear:
                            print(f"Δ Caixa de entrada de {nome_arquivo} foi limpa.")
                            # atualizar o auto_clear_date para a data de hoje
                            escrever_config('auto_clear_date', datetime.now().date())
                    else:
                        pass

                    try:
                        while True:
                            verificar_data = comparar_datas(data_hoje)  # Retorna True se as datas forem diferentes

                            if verificar_data:
                                data_hoje = datetime.now().date()
                                folder = pasta_hoje_path(data_hoje)
                                print(f"Δ Criando pasta para data {data_hoje}")
                                pasta_hoje = criando_pasta_hoje(folder)
                                diretorio_hoje = folder
                                time.sleep(10)
                                if pasta_hoje:
                                    print(f"Δ Pasta de hoje criada com sucesso: {folder}")
                                    time.sleep(10)
                                else:
                                    diretorio_hoje = SAVE_DIR
                                    print("Δ Houve algum erro ao criar a pasta do dia de hoje.\n"
                                          f"Δ Salvando no diretório: {diretorio_hoje}\n")
                                    time.sleep(6)

                            messages = filtro(service)

                            if not messages:
                                print("Δ Não foram encontrados emails não lidos no dia de hoje.")
                                print("")
                                contador_segundos(60, f"para adquirir nova "
                                                      f"lista de emails na conta: {nome_arquivo}")

                                n += 1
                                while n <= 3:
                                    print(f"Δ Tentativas: {n} de 3")
                                    print("")
                                    time.sleep(1)
                                    break

                                if n > 2:
                                    print(f"Δ Não foram encontrados emails não lidos em: {nome_arquivo}")
                                    time.sleep(3)

                                    os.system('cls' if os.name == 'nt' else 'clear')  # Limpa o console

                                    print("Δ Analisando a próxima conta...")
                                    time.sleep(5)
                                    numero_escolhido += 1
                                    n = 0
                                    if numero_escolhido > len(gmails):
                                        numero_escolhido = 1
                                    break
                            else:
                                quantidade_email = len(messages)

                                print(f"Δ Emails não lidos encontrados: {quantidade_email} ")
                                n = 0
                                time.sleep(3)
                                break  # Sair do loop interno quando houver mensagens

                        for message in messages:
                            ordem_lista = messages[ordem]

                            print(f"Δ Conta: {nome_arquivo}")
                            success = baixar_anexos(service, 'me', ordem_lista['id'], diretorio_hoje)

                            # Marcar e-mail como lido dependendo do sucesso do download
                            if success:
                                quantidade_email -= 1
                                try:
                                    marcar_como_lido(service, 'me', ordem_lista['id'])
                                    print(f"Δ Restam: {quantidade_email} e-mails")
                                except Exception as e:
                                    print(f"Δ Erro ao marcar email como lido: {e}, email id:{ordem_lista['id']}")
                                    time.sleep(30)
                            messages.pop(int(ordem))
                        time.sleep(4)
                    except Exception as e:
                        print(f'Δ Ocorreu um erro: {e}')
                        time.sleep(5)
                        c = checar_conexao()
                        while not c:
                            c = checar_conexao()
                            print("Sem conexão com a internet. Tentando reconectar...")
                            time.sleep(5)
                        print("Conexão restabelecida.")
                        time.sleep(5)

                elif numero_escolhido == 0:
                    # Monitorar uma única conta #Implementar
                    print("Essa funcionalidade ainda não foi implementada.")
                    contador_segundos(5, "para retornar ao menu principal.")
                    break

                elif numero_escolhido == -1:
                    creds = gerar_token()
                    email = obter_email(creds)
                    salvar_credencial_unica(creds, email)
                    break

                elif numero_escolhido == -2:
                    # "(-2 ) Escolher data, hora e ordem em que baixar os anexos \n"  # Implementar
                    d = datetime.now().date()
                    d_formatada = d.strftime("%d/%m/%Y")
                    h = datetime.now().strftime("%H:%M:%S")

                    print("Configurando data, hora e ordem de download dos anexos:")
                    data = input(f"Qual data deseja baixar anexos? (Ex: {d_formatada})\n"
                                 f"Digite a data: ")
                    print("")
                    hora = input(f"Qual hora? (Ex:{h})\n"
                                 f"Digite a hora: ")
                    print("")
                    ordem = int(input("Escolha a ordem:\n"
                                      "1) (antigo-->recente) Do mais antigo para o mais recente \n"
                                      "2) (recente-->antigo) Do mais recente para o mais antigo \n"
                                      "Δ Digite: "))
                    print("Essa funcionalidade ainda não foi implementada.")
                    print("")
                    contador_segundos(5, "para voltar ao menu inicial.")
                    break

                elif numero_escolhido == -3:
                    print("Δ Qual conta deseja deletar?")
                    for i, arquivo in enumerate(gmails, start=1):
                        print(f"{i}. {arquivo}")
                    num = int(input("Δ Escolha o número da conta a ser DELETADA: "))
                    ex = deletar_conta(num, gmails)
                    if ex:
                        print(f"Δ Arquivo {gmails[num - 1]} foi deletado.")
                        time.sleep(5)
                    break

                elif numero_escolhido == -4:
                    os.remove(SAVE_DIR)
                    print("Δ O caminho para o diretório de downloads foi excluido. O programa será reiniciado para\n"
                          "que um novo diretório seja escolhido.")
                    time.sleep(7)
                    try:
                        reiniciar_programa()
                    except:
                        exit()

                elif numero_escolhido == -5:
                    r = int(input("Δ Qual conta você deseja limpar e-mails lidos da Caixa de Entrada(INBOX)?\n"
                                  "1. Limpar e-mails lidos de todas as contas\n"
                                  "2. Escolher uma conta\n"
                                  "Δ Digite: "))
                    if r == 1:
                        pass
                    elif r == 2:
                        print("Δ Escolha o número da conta na "
                              "qual deseja limpar a Caixa de Entrada(INBOX):")
                        for i, arquivo in enumerate(gmails, start=1):
                            print(f"( {i} ) {arquivo}")
                        e = int(input("Δ Digite: "))
                        if 1 <= e <= len(gmails):
                            conta = gmails[e - 1]
                            service = verificar_conta(conta)
                            remover_string = '_token.json'
                            nome_arquivo = conta.replace(remover_string, "")
                            time.sleep(5)
                            print(f"Δ Limpando Caixa de Entranda de {nome_arquivo}, aguarde...")
                            c = limpar_inbox(service)
                            if c:
                                print(
                                    f"Δ E-mails lidos da Caixa de entrada da conta {nome_arquivo} foram limpos com sucesso.")
                                time.sleep(5)
                                break
                            else:
                                print(f"Δ Erro ao limpar Caixa de Entrada na conta {nome_arquivo}")
                                time.sleep(5)
                                break
                    else:
                        print("Δ Escolha inválida")
                        time.sleep(5)
                        break

                else:
                    print(
                        "Δ Número inválido. Por favor, escolha um número válido. Ou certifique-se de que o número escolhido é referente a uma conta."
                        "Caso não haja contas, adicione uma antes de prosseguir.")
                    time.sleep(10)
                    break
        except KeyboardInterrupt as k:
            # Caso o usuário aperte Ctrl + C o programa será resetado para o menu de seleção de contas
            print(f"Δ Programa foi resetado: {k}")
            contador_segundos(5, 'para voltar ao menu inicial...')
            os.system('cls' if os.name == 'nt' else 'clear')  # Limpa o console

        except ValueError as e:
            print(f"Δ Você digitou uma STRING. Encerrando programa...: {e}")
            time.sleep(5)

        except Exception as e:
            print(f'Δ Ocorreu um erro: {e}')
            c = checar_conexao()
            while not c:
                c = checar_conexao()
                print("Sem conexão com a internet. Tentando conectar...")
                time.sleep(5)
            print("Conexão estabelecida.\n"
                  "Será necessário selecionar uma conta novamente.")
            time.sleep(5)


if __name__ == '__main__':
    main()
